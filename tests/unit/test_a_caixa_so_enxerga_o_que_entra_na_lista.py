"""A caixa da extensão só enxerga o que entra na lista: nada do diário, da identidade do computador
nem dos endereços dos controles.

A sonda roda pela linha que o produto monta (``comando_na_caixa``), com permissões vazias, e só
CONTA o que acha: nenhum endereço nem identidade sai da sonda.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto

__all__ = ["curto"]

_SONDA = r"""
import glob, json, os
def ler(p):
    try:
        with open(p, 'rb') as f:
            return f.read()
    except OSError:
        return b''
def legiveis(p):
    n = 0
    for raiz, _, arqs in os.walk(p):
        for a in arqs:
            n += bool(ler(os.path.join(raiz, a))[:1])
    return n
uniq = 0
for u in glob.glob('/sys/class/hidraw/*/device/uevent'):
    for linha in ler(u).splitlines():
        uniq += linha.startswith(b'HID_UNIQ=') and len(linha) > len(b'HID_UNIQ=')
print(json.dumps({
    'diario': legiveis('/var/log/journal') + legiveis('/run/log/journal'),
    'machine_id': len(ler('/etc/machine-id').strip()),
    'uniq': uniq,
    'bateria': len([p for p in glob.glob('/sys/class/power_supply/*') if ':' in p]),
    'redes': len([a for a in glob.glob('/sys/class/net/*/address')
                  if ler(a).strip() not in (b'', b'00:00:00:00:00:00')]),
    'var_lib': os.path.exists('/var/lib'), 'var_log': os.path.exists('/var/log'),
    'python': True}))
"""


def _manifesto(*permissoes: str) -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": list(permissoes),  # (noqa-acento)
    })


def _de_dentro(base: Path, manifesto: Manifesto) -> dict[str, object]:
    fonte, dados, casa = base / "fonte", base / "dados", base / "casa"
    for pasta in (fonte, dados, casa):
        pasta.mkdir(exist_ok=True)
    porta = base / "porta.sock"
    porta.touch()
    argv = sup.comando_na_caixa(
        bwrap=shutil.which("bwrap") or "bwrap", comando=[sys.executable, "-c", _SONDA],
        codigo=fonte, dados=dados, porta=porta, manifesto=manifesto, casa=casa, execucao=())
    feito = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    assert feito.returncode == 0, feito.stderr[-400:]
    visto: dict[str, object] = json.loads(feito.stdout)
    return visto


@pytest.mark.parametrize("rede", ["rede:nenhuma", "rede:internet"])
def test_a_sonda_pela_linha_do_produto_nao_acha_nada_da_maquina(curto: Path, rede: str) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: a sonda conta zero do que é da máquina."""
    exigir_caixa_do_bwrap()
    visto = _de_dentro(curto, _manifesto(rede))
    assert visto == {"diario": 0, "machine_id": 0, "uniq": 0, "bateria": 0, "redes": 0,
                     "var_lib": False, "var_log": False, "python": True}


def test_a_raiz_que_e_link_entra_so_quando_o_alvo_tambem_entra(tmp_path: Path) -> None:
    (tmp_path / "usr" / "bin").mkdir(parents=True)
    (tmp_path / "home" / "outro").mkdir(parents=True)
    (tmp_path / "bin").symlink_to("usr/bin")
    (tmp_path / "lib64").symlink_to(tmp_path / "home" / "outro")
    raizes = tuple(str(tmp_path / x) for x in ("usr", "bin", "lib64", "nao-existe"))
    assert sup._o_que_entra(raizes) == [
        "--ro-bind", str(tmp_path / "usr"), str(tmp_path / "usr"),
        "--symlink", "usr/bin", str(tmp_path / "bin")]


def test_o_executavel_fora_da_lista_roda_pelo_alvo_real(tmp_path: Path) -> None:
    alvo = tmp_path / "real-python"
    alvo.touch()
    link = tmp_path / "venv" / "python3"
    link.parent.mkdir()
    link.symlink_to(alvo)
    argv: list[str] = []
    feito = sup._executavel_a_vista([str(link), "-I"], (str(tmp_path),), argv)
    assert feito == [str(link), "-I"] and argv == []
    argv = []
    feito = sup._executavel_a_vista([str(link)], ("/usr",), argv)
    assert feito == [str(alvo)] and argv == ["--ro-bind", str(alvo), str(alvo)]
    assert sup._executavel_a_vista(["python3"], ("/usr",), argv) == ["python3"]


def test_o_executavel_do_opt_leva_a_pasta_dele(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    programa = tmp_path / "opt" / "app" / "bin" / "app"
    programa.parent.mkdir(parents=True)
    programa.touch()
    monkeypatch.setattr(sup, "PASTA_DOS_PROGRAMAS", str(tmp_path / "opt"))
    argv: list[str] = []
    assert sup._executavel_a_vista([str(programa)], ("/usr",), argv) == [str(programa)]
    assert argv == ["--ro-bind", str(tmp_path / "opt" / "app"), str(tmp_path / "opt" / "app")]


def test_do_sys_volta_so_o_aparelho_do_no() -> None:
    real = "/sys/devices/virtual/mem/null"
    if not Path(real).is_dir():
        pytest.skip("sem o /sys do /dev/null")
    assert sup._o_sys_dos_aparelhos(["/dev/null", "/dev/nao-existe"]) == [
        "--ro-bind", real, real, "--symlink", real, "/sys/dev/char/1:3",
        "--symlink", real, "/sys/class/mem/null"]
