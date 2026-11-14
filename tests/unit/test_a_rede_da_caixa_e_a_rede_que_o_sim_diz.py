"""A rede da caixa e a rede que o «sim» diz (A-REDE-DA-CAIXA-E-A-REDE-QUE-O-SIM-DIZ-01).

Com o ``pasta``, a caixa com rede ganha um espaço de rede exclusivo: os sockets abstratos da casa (o
do XWayland, por exemplo) somem de dentro. A frase da rede diz o que o «sim» abre de fato.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto

__all__ = ["curto"]


def _manifesto(*permissoes: str) -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": list(permissoes),  # (noqa-acento)
    })


def caixa(base: Path, manifesto: Manifesto, comando: list[str]) -> list[str]:
    fonte, dados, casa = base / "fonte", base / "dados", base / "casa"
    for pasta in (fonte, dados, casa):
        pasta.mkdir(exist_ok=True)
    porta = base / "porta.sock"
    porta.touch()
    return sup.comando_na_caixa(bwrap=shutil.which("bwrap") or "bwrap", comando=comando,
                                codigo=fonte, dados=dados, porta=porta, manifesto=manifesto,
                                casa=casa, execucao=())


def exigir_o_pasta() -> None:
    exigir_caixa_do_bwrap()
    if sup.rede_propria_da_caixa() is None:
        pytest.skip("sem o pasta, a caixa com rede fica no espaço de rede da casa")


@pytest.mark.parametrize("rede", ["rede:local", "rede:internet"])
def test_com_o_pasta_o_socket_abstrato_da_casa_nao_atende(curto: Path, rede: str) -> None:
    exigir_o_pasta()
    ouvinte = socket.socket(socket.AF_UNIX)
    nome = f"\0hefesto-teste-x11-{os.getpid()}"
    ouvinte.bind(nome)
    ouvinte.listen(1)
    sonda = ("import socket\ns = socket.socket(socket.AF_UNIX)\n"
             f"try:\n    s.connect({nome!r}); print('atendeu')\n"
             "except OSError as e:\n    print(type(e).__name__)\n")
    try:
        feito = subprocess.run(caixa(curto, _manifesto(rede), ["/usr/bin/python3", "-c", sonda]),
                               capture_output=True, text=True, timeout=60, check=False)
    finally:
        ouvinte.close()
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.strip() == "ConnectionRefusedError", feito.stdout


def test_a_linha_da_caixa_com_rede_sai_pelo_pasta(curto: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: "/usr/bin/pasta")
    argv = caixa(curto, _manifesto("rede:internet"), ["true"])
    assert argv[0] == "/usr/bin/pasta" and "--unshare-net" not in argv
    assert argv[argv.index("--") + 1].endswith("bwrap")
    nenhuma = caixa(curto, _manifesto("rede:nenhuma"), ["true"])
    assert nenhuma[0].endswith("bwrap") and "--unshare-net" in nenhuma
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: None)
    casa = caixa(curto, _manifesto("rede:local"), ["true"])
    assert casa[0].endswith("bwrap") and "--unshare-net" not in casa


def test_a_frase_da_rede_diz_o_que_o_sim_abre(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: "/usr/bin/pasta")
    assert sup.frase_da_rede(_manifesto("rede:local")) == sup.A_REDE_INCLUI_A_INTERNET
    assert sup.frase_da_rede(_manifesto("rede:internet")) == ""
    assert sup.frase_da_rede(_manifesto("rede:nenhuma")) == ""
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: None)
    for rede in ("rede:local", "rede:internet"):
        assert sup.frase_da_rede(_manifesto(rede)) == sup.A_REDE_INCLUI_A_MAQUINA
    assert sup.frase_da_rede(_manifesto("rede:nenhuma")) == ""
