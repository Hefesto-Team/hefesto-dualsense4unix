"""A rede da caixa e a rede que o «sim» diz (A-REDE-DA-CAIXA-E-A-REDE-QUE-O-SIM-DIZ-01).

Sem o ``pasta``, a caixa com rede fica no espaço de rede da casa: o jogo alcança a ponte que a
extensão abre no ``127.0.0.1`` (o Game Mode da Lovense em 20010 e 30010), e a extensão alcança o app
que a pessoa abriu na máquina (o Intiface Central em 12345). Com ele, só pelas ``portas`` declaradas
(test_a_caixa_com_rede_abre_so_as_portas_declaradas). A frase da rede diz o que o «sim» abre.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import time
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


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


_PONTE = """
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", int(sys.argv[1])))
s.listen(1)
print("ouvindo", flush=True)
s.settimeout(15)
try:
    s.accept()
    print("o jogo chegou", flush=True)
except OSError as exc:
    print(type(exc).__name__, flush=True)
"""


@pytest.mark.parametrize("rede", ["rede:local", "rede:internet"])
def test_o_jogo_da_casa_alcanca_a_ponte_da_extensao(curto: Path, rede: str) -> None:
    exigir_caixa_do_bwrap()
    porta = _porta_livre()
    filho = subprocess.Popen(
        caixa(curto, _manifesto(rede), ["/usr/bin/python3", "-c", _PONTE, str(porta)]),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert filho.stdout is not None
        assert filho.stdout.readline().strip() == "ouvindo"
        prazo = time.monotonic() + 5
        while True:
            try:
                with socket.create_connection(("127.0.0.1", porta), timeout=1):
                    break
            except OSError:
                if time.monotonic() > prazo:
                    pytest.fail("o jogo da casa não alcança a ponte da extensão no 127.0.0.1")
                time.sleep(0.1)
        saida, _ = filho.communicate(timeout=20)
        assert "o jogo chegou" in saida, saida
    finally:
        if filho.poll() is None:
            filho.kill()
            filho.wait()


_CLIENTE = """
import socket, sys
s = socket.socket()
s.settimeout(3)
try:
    s.connect(("127.0.0.1", int(sys.argv[1]))); print("chegou")
except OSError as exc:
    print(type(exc).__name__)
"""


@pytest.mark.parametrize("rede", ["rede:local", "rede:internet"])
def test_a_extensao_alcanca_o_app_que_a_pessoa_abriu_na_maquina(curto: Path, rede: str) -> None:
    exigir_caixa_do_bwrap()
    with socket.socket() as app:
        app.bind(("127.0.0.1", 0))
        app.listen(1)
        feito = subprocess.run(
            caixa(curto, _manifesto(rede),
                  ["/usr/bin/python3", "-c", _CLIENTE, str(app.getsockname()[1])]),
            capture_output=True, text=True, timeout=60, check=False)
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.strip() == "chegou", feito.stdout


def test_a_linha_da_caixa_so_corta_a_rede_na_rede_nenhuma(curto: Path) -> None:
    for rede in ("rede:local", "rede:internet"):
        argv = caixa(curto, _manifesto(rede), ["true"])
        assert argv[0].endswith("bwrap") and "--unshare-net" not in argv, rede
    nenhuma = caixa(curto, _manifesto("rede:nenhuma"), ["true"])
    assert nenhuma[0].endswith("bwrap") and "--unshare-net" in nenhuma


def test_a_frase_da_rede_diz_o_que_o_sim_abre(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: None)
    for rede in ("rede:local", "rede:internet"):
        assert sup.frase_da_rede(_manifesto(rede)) == sup.A_REDE_INCLUI_A_MAQUINA
    assert sup.frase_da_rede(_manifesto("rede:nenhuma")) == ""
