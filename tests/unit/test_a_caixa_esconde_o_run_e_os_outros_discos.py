"""A caixa esconde o run e os outros discos (A-CAIXA-ESCONDE-O-RUN-E-OS-OUTROS-DISCOS-01).

De dentro da caixa da extensão, nenhum socket de ``/run`` (o do broker, o do docker) atende e os
outros discos (``/mnt``, ``/media``, ``/srv``, ``/home``) somem; volta só o que a permissão pede.
A caixa do leitor e do fixador cobre o ``/run`` inteiro.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto

__all__ = ["curto"]

BROKER = "/run/hefesto-hidraw-broker/broker.sock"

_OLHAR = """
import json, os, socket, sys
fora = {}
for caminho in sys.argv[1:]:
    if caminho.endswith(".sock"):
        s = socket.socket(socket.AF_UNIX)
        try:
            s.connect(caminho)
            fora[caminho] = "atendeu"
        except OSError as e:
            fora[caminho] = e.__class__.__name__
        finally:
            s.close()
    else:
        fora[caminho] = os.path.exists(caminho)
print(json.dumps(fora))
"""


def _manifesto(*permissoes: str) -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": list(permissoes),  # (noqa-acento)
    })


def _caixa(base: Path, manifesto: Manifesto, comando: list[str]) -> list[str]:
    fonte, dados, casa = base / "fonte", base / "dados", base / "casa"
    for pasta in (fonte, dados, casa):
        pasta.mkdir(exist_ok=True)
    porta = base / "porta.sock"
    porta.touch()
    return sup.comando_na_caixa(bwrap=shutil.which("bwrap") or "bwrap", comando=comando,
                                codigo=fonte, dados=dados, porta=porta, manifesto=manifesto,
                                casa=casa, execucao=())


@pytest.fixture
def run_e_mnt_de_mentira(curto: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Um ``/run`` com um socket ouvindo e um ``/mnt`` com uma pasta, fora do ``/tmp``."""
    run, mnt = curto / "run", curto / "mnt"
    (run / "hidraw").mkdir(parents=True)
    (mnt / "Disco").mkdir(parents=True)
    ouvinte = socket.socket(socket.AF_UNIX)
    ouvinte.bind(str(run / "hidraw" / "broker.sock"))
    ouvinte.listen(1)
    monkeypatch.setattr(censo, "_execucao_escondida", lambda real=censo._execucao_escondida:
                        (*real(), str(run)))
    try:
        yield run / "hidraw" / "broker.sock", mnt / "Disco"
    finally:
        ouvinte.close()


def _de_dentro(argv: list[str]) -> dict[str, object]:
    feito = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    assert feito.returncode == 0, feito.stderr
    resposta: dict[str, object] = json.loads(feito.stdout)
    return resposta


def _alvos(broker: Path, disco: Path) -> list[str]:
    return [str(broker), str(disco), BROKER, "/run/docker.sock", "/mnt", "/home"]


@pytest.mark.parametrize("rede", ["rede:nenhuma", "rede:internet"])
def test_de_dentro_da_caixa_o_socket_do_run_nao_atende_e_o_disco_some(
        curto: Path, run_e_mnt_de_mentira: tuple[Path, Path], rede: str) -> None:
    exigir_caixa_do_bwrap()
    broker, disco = run_e_mnt_de_mentira
    probe = socket.socket(socket.AF_UNIX)
    probe.connect(str(broker))
    probe.close()
    alvos = _alvos(broker, disco)
    visto = _de_dentro(_caixa(curto, _manifesto(rede), [sys.executable, "-c", _OLHAR, *alvos]))
    assert visto[str(broker)] in ("FileNotFoundError", "ConnectionRefusedError"), visto
    assert visto[str(disco)] is False, visto
    assert visto[BROKER] in ("FileNotFoundError", "ConnectionRefusedError"), visto
    assert visto["/run/docker.sock"] in ("FileNotFoundError", "ConnectionRefusedError"), visto
    assert not any(visto[c] == "atendeu" for c in alvos)


def test_a_caixa_do_leitor_cobre_o_run(
        curto: Path, run_e_mnt_de_mentira: tuple[Path, Path]) -> None:
    exigir_caixa_do_bwrap()
    broker, disco = run_e_mnt_de_mentira
    alvos = _alvos(broker, disco)
    (curto / "fonte").mkdir(exist_ok=True)
    leitor = censo.LeitorPorProcesso("e", "E", (sys.executable,), curto / "fonte")
    argv = censo.linha_do_leitor(leitor, [sys.executable, "-c", _OLHAR, *alvos],
                                 shutil.which("bwrap"))
    visto = _de_dentro(argv)
    assert visto[str(broker)] in ("FileNotFoundError", "ConnectionRefusedError"), visto
    assert visto[BROKER] in ("FileNotFoundError", "ConnectionRefusedError"), visto
    fixador = censo.FixadorPorProcesso("e", "E", (sys.executable,), curto / "fonte", ())
    argv = censo.linha_do_fixador(fixador, [sys.executable, "-c", _OLHAR, *alvos],
                                  shutil.which("bwrap"), curto)
    visto = _de_dentro(argv)
    assert visto[str(broker)] in ("FileNotFoundError", "ConnectionRefusedError"), visto


def test_volta_so_o_que_a_permissao_pede(curto: Path) -> None:
    def montados(*permissoes: str) -> set[str]:
        argv = _caixa(curto, _manifesto(*permissoes), ["true"])
        return {argv[i + 1] for i, a in enumerate(argv) if a == "--ro-bind"}

    sem = montados("rede:nenhuma")
    assert not any(c.startswith("/run/") for c in sem), sem
    if os.path.isdir("/run/systemd/resolve"):
        assert "/run/systemd/resolve" in montados("rede:internet")
    assert "/run/dbus" not in montados("rede:nenhuma", "bluetooth")
    assert "/run/dbus" not in montados("rede:internet")
    argv = _caixa(curto, _manifesto("rede:nenhuma"), ["true"])
    for flag in ("--unshare-ipc", "--unshare-uts", "--unshare-cgroup-try", "--unshare-pid"):
        assert flag in argv
    montadas = [argv[i + 1] for i, a in enumerate(argv) if a in ("--ro-bind", "--bind")]
    assert "/" not in montadas
    da_caixa = {str(curto / "fonte"), str(curto / "dados"), str(curto / "porta.sock")}
    assert not any(c == raiz or c.startswith(f"{raiz}/") for c in set(montadas) - da_caixa
                   for raiz in ("/run", "/var", "/mnt", "/media", "/srv", "/home"))


def test_o_executavel_fora_da_lista_roda_pelo_alvo_real(tmp_path: Path) -> None:
    alvo = tmp_path / "real-python"
    alvo.touch()
    link = tmp_path / "venv" / "python3"
    link.parent.mkdir()
    link.symlink_to(alvo)
    argv: list[str] = []
    feito = sup._executavel_a_vista([str(link), "-I"], (str(tmp_path),), argv)
    assert feito == [str(link), "-I"] and argv == []
    feito = sup._executavel_a_vista([str(link)], ("/usr",), argv)
    assert feito == [str(alvo)] and argv == ["--ro-bind", str(alvo), str(alvo)]
    assert sup._executavel_a_vista(["python3"], ("/usr",), argv) == ["python3"]
