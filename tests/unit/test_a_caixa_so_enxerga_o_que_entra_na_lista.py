"""A caixa da extensão só enxerga o que entra na lista: nada do diário, da identidade do computador
nem dos endereços dos controles.

A sonda roda pela linha que o produto monta (``comando_na_caixa``), com permissões vazias, e só
CONTA o que acha: nenhum endereço nem identidade sai da sonda.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto, aparelhos_do_sim
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
for u in [*glob.glob('/sys/class/hidraw/*/device/uevent'),
          *glob.glob('/sys/bus/hid/devices/*/uevent')]:
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
    'hci': sorted(p for p in os.listdir('/sys/class/bluetooth') if ':' not in p)
           if os.path.isdir('/sys/class/bluetooth') else [],
    'hid': bool(glob.glob('/sys/bus/hid/devices/*')),
    'python': True}))
"""


_E429 = {"classe": "hidraw", "vid": "1a86", "pid": "e429", "nome": "o adaptador",
         "pela_porta": True}
_DA_FABRICANTE = bytes.fromhex("06a0ff0901a1010901150026ff00750895408102c0")


def _manifesto(*permissoes: str, aparelhos: tuple[dict[str, object], ...] = ()) -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": list(permissoes), "aparelhos": list(aparelhos),  # (noqa-acento)
    })


def _do_computador(bluetooth: bool) -> tuple[list[str], bool]:
    classe = Path("/sys/class/bluetooth")
    hci = sorted(p.name for p in classe.iterdir() if ":" not in p.name) if classe.is_dir() else []
    return (hci, any(Path("/sys/bus/hid/devices").glob("*"))) if bluetooth else ([], False)


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


@pytest.mark.parametrize("pedidas", [
    ("rede:nenhuma",), ("rede:internet",), ("aparelhos", "bluetooth", "rede:internet")])
def test_a_sonda_pela_linha_do_produto_nao_acha_nada_da_maquina(
        curto: Path, pedidas: tuple[str, ...]) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: a sonda conta zero do que é da máquina."""
    exigir_caixa_do_bwrap()
    hci, hid = _do_computador("bluetooth" in pedidas)
    visto = _de_dentro(curto, _manifesto(*pedidas))
    assert visto == {"diario": 0, "machine_id": 0, "uniq": 0, "bateria": 0, "redes": 0,
                     "var_lib": False, "var_log": False, "hci": hci, "hid": hid, "python": True}


def test_a_raiz_que_e_link_entra_so_quando_o_alvo_tambem_entra(tmp_path: Path) -> None:
    (tmp_path / "usr" / "bin").mkdir(parents=True)
    (tmp_path / "home" / "outro").mkdir(parents=True)
    (tmp_path / "bin").symlink_to("usr/bin")
    (tmp_path / "lib64").symlink_to(tmp_path / "home" / "outro")
    raizes = tuple(str(tmp_path / x) for x in ("usr", "bin", "lib64", "nao-existe"))
    assert sup._o_que_entra(raizes) == [
        "--ro-bind", str(tmp_path / "usr"), str(tmp_path / "usr"),
        "--symlink", "usr/bin", str(tmp_path / "bin")]


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


def test_o_pela_porta_entra_so_no_sys(curto: Path) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: o nó pela porta fica fora, o /sys entra."""
    real = os.path.realpath("/sys/dev/char/5:0")
    if not real.startswith("/sys/devices/"):
        pytest.skip("sem o /sys do /dev/tty")
    for pasta in ("fonte", "dados", "casa"):
        (curto / pasta).mkdir()
    argv = sup.comando_na_caixa(
        bwrap="bwrap", comando=["true"], codigo=curto / "fonte", dados=curto / "dados",
        porta=curto / "porta.sock", manifesto=_manifesto("aparelhos"), casa=curto / "casa",
        execucao=(), pela_porta=("/dev/tty",))
    assert "/dev/tty" not in argv[:argv.index("--")]
    assert ["--symlink", real, "/sys/dev/char/5:0"] in [argv[i:i + 3] for i in range(len(argv))]


def _usb(hub: Path, nome: str, hid: str, hidraw: str) -> Path:
    """Um aparelho USB ``nome`` no ``hub``, com um HID e o ``hidraw`` dele, como no ``/sys``."""
    pasta = hub / nome
    no = pasta / f"{nome}:1.0" / hid / "hidraw" / hidraw
    no.mkdir(parents=True)
    for arquivo, valor in (("idVendor", "1a86"), ("idProduct", "e429")):
        (pasta / arquivo).write_text(valor + "\n")
    (no.parents[1] / "uevent").write_text("HID_ID=0003:00001A86:0000E429\nHID_UNIQ=forjado\n")
    (no.parents[1] / "report_descriptor").write_bytes(_DA_FABRICANTE)
    (no / "device").symlink_to(no.parents[1])
    return no


_OLHA_O_HUB = r"""
import glob, json, os, sys
def ver():
    usb = '/sys/bus/usb/devices/3-1.4'
    return {'idVendor': os.path.isfile(usb + '/idVendor'),
            'hidraw': sorted(os.path.basename(p) for p in glob.glob(usb + '/*/*/hidraw/*')),
            'vizinho': os.path.exists(sys.argv[1])}
antes = ver()
print('pronto', flush=True)
sys.stdin.readline()
print(json.dumps({'antes': antes, 'depois': ver()}))
"""


def test_o_aparelho_usb_vem_pelo_hub_vivo_com_os_vizinhos_cobertos(curto: Path) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: o USB que volta do RESET segue à vista."""
    exigir_caixa_do_bwrap()
    hub = curto / "sys" / "devices" / "usb3" / "3-1"
    real = _usb(hub, "3-1.4", "0003:1A86:E429.0001", "hidraw7")
    vizinho = _usb(hub, "3-1.2", "0003:1A86:E429.0002", "hidraw4").parents[1] / "uevent"
    argv = [shutil.which("bwrap") or "bwrap", *sup._o_que_entra(sup.ENTRAM_NA_CAIXA),
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/sys",
            *sup._o_sys_dos_achados([("/sys/dev/char/240:7", str(real))])]
    comando = sup._executavel_a_vista([sys.executable, "-c", _OLHA_O_HUB, str(vizinho)],
                                      sup.ENTRAM_NA_CAIXA, argv)
    with subprocess.Popen([*argv, "--", *comando], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as caixa:
        assert caixa.stdout is not None and caixa.stderr is not None
        assert caixa.stdout.readline() == "pronto\n", caixa.stderr.read()[-400:]
        shutil.rmtree(hub / "3-1.4")
        _usb(hub, "3-1.4", "0003:1A86:E429.0003", "hidraw9")
        saida, erro = caixa.communicate("\n", timeout=60)
    assert caixa.returncode == 0, erro[-400:]
    visto = json.loads(saida)
    assert visto["antes"] == {"idVendor": True, "hidraw": ["hidraw7"], "vizinho": False}
    assert visto["depois"] == {"idVendor": True, "hidraw": ["hidraw9"], "vizinho": False}


def _vigia(manifesto: Manifesto, sys_: Path, monkeypatch: pytest.MonkeyPatch
           ) -> tuple[sup.Supervisor, list[str]]:
    real = sup.pastas_pela_porta
    monkeypatch.setattr(sup, "pastas_pela_porta", lambda m, a, *_: real(m, a, sys_))
    monkeypatch.setattr(sup, "aparelhos_que_casam", lambda *_: ())

    class Processo:
        returncode = None

    reabertas: list[str] = []
    aceitos = tuple(aparelhos_do_sim(manifesto))
    supervisor = sup.Supervisor.__new__(sup.Supervisor)
    supervisor.bwrap = "/usr/bin/bwrap"
    supervisor._registro_lido = {"exemplo": object()}  # type: ignore[dict-item]
    supervisor._reaberta_pelo_aparelho = {}
    vigiada = sup._Vigiada("exemplo", processo=Processo(),  # type: ignore[arg-type]
                           manifesto=manifesto, aceitos=aceitos)

    async def comecar(_entrada: object) -> None:
        reabertas.append("exemplo")
        vigiada.pela_porta = frozenset(sup.pastas_pela_porta(manifesto, aceitos).values())
        vigiada.aparelho_novo = False

    supervisor._vigiadas = {"exemplo": vigiada}
    supervisor._comecar = comecar  # type: ignore[method-assign]
    vigiada.pela_porta = frozenset(sup.pastas_pela_porta(manifesto, aceitos).values())
    return supervisor, reabertas


def _ligar(sys_: Path, hid: str, hidraw: str, *, de_novo: bool = False) -> None:
    hub = sys_ / "devices" / "usb3" / "3-1"
    if de_novo:
        shutil.rmtree(hub / "3-1.4")
        shutil.rmtree(sys_ / "class" / "hidraw")
    no = _usb(hub, "3-1.4", hid, hidraw)
    (sys_ / "class" / "hidraw").mkdir(parents=True, exist_ok=True)
    (sys_ / "class" / "hidraw" / hidraw).symlink_to(no)


def test_o_pela_porta_reabre_so_quando_o_aparelho_nao_estava_no_sys_da_caixa(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: o ligado depois reabre; o RESET, não."""
    sys_ = tmp_path / "sys"
    (sys_ / "class" / "hidraw").mkdir(parents=True)
    manifesto = _manifesto("aparelhos", aparelhos=(_E429,))
    supervisor, reabertas = _vigia(manifesto, sys_, monkeypatch)

    async def voltas(n: int) -> None:
        for _ in range(n):
            await supervisor._conferir_os_aparelhos()

    asyncio.run(voltas(3))
    assert reabertas == []
    _ligar(sys_, "0003:1A86:E429.0001", "hidraw7")
    assert sup.pastas_pela_porta(manifesto, aparelhos_do_sim(manifesto), sys_) == {
        "/dev/hidraw7": os.path.realpath(sys_ / "devices" / "usb3" / "3-1" / "3-1.4")}
    asyncio.run(voltas(3))
    assert reabertas == ["exemplo"], "o adaptador ligado depois da abertura entra no /sys"
    for numero in range(8, 12):
        _ligar(sys_, f"0003:1A86:E429.{numero:04d}", f"hidraw{numero}", de_novo=True)
        asyncio.run(voltas(3))
    assert reabertas == ["exemplo"], "o que volta do RESET; na mesma porta não reabre a caixa"
