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
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

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
    radio = any(p.name.startswith("0005:") for p in Path("/sys/bus/hid/devices").glob("*"))
    return (hci, radio) if bluetooth else ([], False)


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


def _usb(hub: Path, nome: str, hid: str, hidraw: str,
         ids: tuple[str, str] = ("1a86", "e429"), uniq: str = "forjado") -> Path:
    """Um aparelho USB ``nome`` no ``hub``, com um HID e o ``hidraw`` dele, como no ``/sys``."""
    pasta = hub / nome
    no = pasta / f"{nome}:1.0" / hid / "hidraw" / hidraw
    no.mkdir(parents=True)
    for arquivo, valor in (("idVendor", ids[0]), ("idProduct", ids[1])):
        (pasta / arquivo).write_text(valor + "\n")
    (no.parents[1] / "uevent").write_text(
        f"HID_ID=0003:0000{ids[0].upper()}:0000{ids[1].upper()}\nHID_UNIQ={uniq}\n")
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
    supervisor._vez_da_vigia = asyncio.Lock()
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


_O_CONTROLE = ("054c", "0ce6")


def _irmao(hub: Path, nome: str, hid: str, bus: Path) -> None:
    """Um controle USB ``nome`` no ``hub``, com o link dele em ``bus``. O que já existe sai depois
    de o novo nascer ao lado: o kernfs nunca repete o ``inode`` (o ext4 repetiria)."""
    hub.mkdir(parents=True, exist_ok=True)
    ao_lado = hub.parent / f"ao-lado-{nome}"
    _usb(ao_lado, nome, hid, "hidraw0", ids=_O_CONTROLE, uniq="02:fe:00:00:00:01")
    if (hub / nome).exists():
        shutil.rmtree(hub / nome)
    (ao_lado / nome).rename(hub / nome)
    ao_lado.rmdir()
    for velho in bus.glob(f"*{nome}*"):
        velho.unlink()
    (bus / f"{hid}-{nome}").symlink_to(hub / nome / f"{nome}:1.0" / hid)


_OLHA_OS_IRMAOS = r"""
import glob, json, os, sys, time
hub, e429 = sys.argv[1], sys.argv[2]
def ler(p):
    try:
        with open(p, 'rb') as f:
            return f.read()
    except OSError:
        return b''
for linha in sys.stdin:
    pedido = linha.split()
    if pedido[:1] == ['fugir']:
        if os.fork() == 0:
            os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNS)
            time.sleep(600)
            os._exit(0)
        time.sleep(0.2)
    uniq = sum(l.startswith(b'HID_UNIQ=02:fe') for u in glob.glob('/sys/bus/hid/devices/*/uevent')
               for l in ler(u).splitlines())
    print(json.dumps({
        'vizinhos': sorted(f for f in os.listdir(hub)
                           if os.path.join(hub, f) != e429
                           and ler(os.path.join(hub, f, 'idVendor'))),
        'uniq': uniq,
        'hid': sorted(os.path.basename(p) for p in glob.glob('/sys/bus/hid/devices/*')),
        'hidraw': sorted(os.path.basename(p) for p in glob.glob(e429 + '/*/*/hidraw/*'))}),
        flush=True)
"""


def _caixa_no_hub(hub: Path, e429: Path, retrato: sup.RetratoDosHubs,
                  hid: dict[str, str], *, fecha: bool = True,
                  por_fora: bool = False) -> subprocess.Popen[str]:
    """A caixa pela linha do produto (o hub vivo e a pasta sintética do HID), no /sys forjado.
    ``por_fora`` a abre dentro de outro espaço de usuário e de PID, como o ``pasta`` faz."""
    real = next(e429.glob("*/*/hidraw/*"))
    bwrap = shutil.which("bwrap") or "bwrap"
    fechada = ["--unshare-user", "--disable-userns"] if fecha and sup.bwrap_fecha_o_userns(
        bwrap) else []
    argv = [bwrap, *fechada, *sup._o_que_entra(sup.ENTRAM_NA_CAIXA),
            "--unshare-pid", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/sys",
            *sup._o_sys_dos_achados([("/sys/dev/char/240:7", str(real))], retrato),
            *sup.a_pasta_do_hid(hid), "--die-with-parent", "--new-session"]
    comando = sup._executavel_a_vista(
        [sys.executable, "-c", _OLHA_OS_IRMAOS, str(hub), str(e429)], sup.ENTRAM_NA_CAIXA, argv)
    fora = ["unshare", "--user", "--map-current-user", "--pid", "--fork"] if por_fora else []
    caixa = subprocess.Popen([*fora, *argv, "--", *comando], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _ver(caixa)
    return caixa


def _ver(caixa: subprocess.Popen[str], pedido: str = "") -> dict[str, Any]:
    assert caixa.stdin is not None and caixa.stdout is not None
    caixa.stdin.write(pedido + "\n")
    caixa.stdin.flush()
    linha = caixa.stdout.readline()
    assert linha, caixa.stderr.read()[-400:] if caixa.stderr else ""
    visto: dict[str, Any] = json.loads(linha)
    return visto


def test_o_irmao_que_o_hub_vivo_mostra_entra_na_vigia(curto: Path) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: o controle ligado depois e o coberto que
    sai e volta aparecem pelo hub vivo; a vigia acha os dois, e quatro RESET; seguidos do
    adaptador nunca entram na vigia."""
    exigir_caixa_do_bwrap()
    hub = curto / "sys" / "devices" / "usb3" / "3-1"
    bus = curto / "bus-hid"
    bus.mkdir()
    _irmao(hub, "3-1.2", "0003:054C:0CE6.0002", bus)
    _usb(hub, "3-1.4", "0003:1A86:E429.0001", "hidraw7")
    retrato: sup.RetratoDosHubs = {}
    with _caixa_no_hub(hub, hub / "3-1.4", retrato, {}) as caixa:
        _irmao(hub, "3-1.3", "0003:054C:0CE6.0003", bus)
        _irmao(hub, "3-1.2", "0003:054C:0CE6.0004", bus)
        assert _ver(caixa)["vizinhos"] == ["3-1.2", "3-1.3"]
        irmaos, sairam = sup.irmaos_a_vista(retrato)
        assert (sorted(irmaos), sairam) == ([str(hub / "3-1.2"), str(hub / "3-1.3")], [])
        caixa.communicate("", timeout=60)
    retrato = {}
    with _caixa_no_hub(hub, hub / "3-1.4", retrato, {}) as caixa:
        for numero in range(8, 12):
            shutil.rmtree(hub / "3-1.4")
            _usb(hub, "3-1.4", f"0003:1A86:E429.{numero:04d}", f"hidraw{numero}")
            assert sup.irmaos_a_vista(retrato) == ({}, []), "o RESET; na mesma porta não entra"
            assert _ver(caixa)["hidraw"] == [f"hidraw{numero}"]
        caixa.communicate("", timeout=60)


_DA_MAQUINA = ("0003:046D:C52B.0001", "0018:04F3:3125.0002", "0005:054C:0CE6.0003",
               "0003:1A86:E429.0004")


def test_a_pasta_do_hid_leva_so_o_radio_e_o_declarado(tmp_path: Path) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: com bluetooth, a pasta sintética leva os
    HID do rádio (0005) e os do VID:PID declarado e aceito; o teclado e o touchpad ficam fora."""
    devices = tmp_path / "bus" / "hid" / "devices"
    devices.mkdir(parents=True)
    for nome in _DA_MAQUINA:
        (devices / nome).symlink_to(f"../../../devices/x/{nome}")
    pedido = _manifesto("aparelhos", "bluetooth", aparelhos=(_E429,))
    aceitos = aparelhos_do_sim(pedido)
    assert sup.hid_da_caixa(pedido, aceitos, tmp_path) == {
        nome: f"../../../devices/x/{nome}" for nome in _DA_MAQUINA[2:]}
    assert list(sup.hid_da_caixa(pedido, (), tmp_path)) == [_DA_MAQUINA[2]]
    assert sup.hid_da_caixa(_manifesto("aparelhos", aparelhos=(_E429,)), aceitos, tmp_path) == {}
    assert sup.a_caixa_quer_saber({"ACTION": "add", "SUBSYSTEM": "usb", "DEVTYPE": "usb_device"})
    assert sup.a_caixa_quer_saber({"ACTION": "remove", "SUBSYSTEM": "hid"})
    assert not sup.a_caixa_quer_saber({"ACTION": "add", "SUBSYSTEM": "usb",
                                       "DEVTYPE": "usb_interface"})


class _Vigia:
    """O supervisor do produto vigiando uma caixa de verdade sobre o /sys forjado."""

    def __init__(self, curto: Path, cascata: str, monkeypatch: pytest.MonkeyPatch,
                 *, fecha: bool = True, por_fora: bool = False) -> None:
        exigir_caixa_do_bwrap()
        self.fecha, self.por_fora = fecha, por_fora
        self.sys_ = curto / "sys"
        self.hub = self.sys_ / "devices" / "usb3" / cascata
        self.bus = self.sys_ / "bus" / "hid" / "devices"
        self.bus.mkdir(parents=True)
        self.e429 = self.hub / f"{self.hub.name}.4"
        (self.sys_ / "class" / "hidraw").mkdir(parents=True)
        _irmao(self.hub, f"{self.hub.name}.2", "0005:054C:0CE6.0002", self.bus)
        self.ligar(7)
        self.manifesto = _manifesto("aparelhos", "bluetooth", aparelhos=(_E429,))
        aceitos = tuple(aparelhos_do_sim(self.manifesto))
        real_pp, real_hid = sup.pastas_pela_porta, sup.hid_da_caixa
        monkeypatch.setattr(sup, "pastas_pela_porta", lambda m, a, *_: real_pp(m, a, self.sys_))
        monkeypatch.setattr(sup, "aparelhos_que_casam", lambda *_: ())
        monkeypatch.setattr(sup, "hid_da_caixa", lambda m, a, *_: real_hid(m, a, self.sys_))
        self.reabertas: list[str] = []
        self.supervisor = sup.Supervisor.__new__(sup.Supervisor)
        self.supervisor.bwrap = "/usr/bin/bwrap"
        self.supervisor._registro_lido = {"exemplo": object()}  # type: ignore[dict-item]
        self.supervisor._reaberta_pelo_aparelho = {}
        self.supervisor._vez_da_vigia = asyncio.Lock()
        self.vigiada = sup._Vigiada("exemplo", manifesto=self.manifesto, aceitos=aceitos)
        self.supervisor._vigiadas = {"exemplo": self.vigiada}

        async def comecar(_entrada: object) -> None:
            self.reabertas.append("exemplo")
            self.abrir()

        self.supervisor._comecar = comecar  # type: ignore[method-assign]
        self.caixa: subprocess.Popen[str] | None = None
        self.abrir()

    def ligar(self, numero: int) -> None:
        """O adaptador liga (ou volta do RESET;) na mesma porta; o novo nasce ao lado antes de o
        velho sair, porque o kernfs nunca repete o ``inode``."""
        ao_lado = self.hub.parent / "ao-lado-do-adaptador"
        _usb(ao_lado, self.e429.name, f"0003:1A86:E429.{numero:04d}", f"hidraw{numero}")
        if self.e429.exists():
            shutil.rmtree(self.e429)
            for velho in (self.sys_ / "class" / "hidraw").iterdir():
                velho.unlink()
            for velho in self.bus.glob("*E429*"):
                velho.unlink()
        (ao_lado / self.e429.name).rename(self.e429)
        ao_lado.rmdir()
        no = next(self.e429.glob(f"*/*/hidraw/hidraw{numero}"))
        (self.sys_ / "class" / "hidraw" / f"hidraw{numero}").symlink_to(no)
        (self.bus / f"0003:1A86:E429.{numero:04d}").symlink_to(no.parents[1])

    def abrir(self) -> None:
        self.fechar()
        if not self.e429.exists():
            self.vigiada.processo = None
            return
        self.vigiada.retrato = {}
        self.vigiada.hid = sup.hid_da_caixa(self.manifesto, self.vigiada.aceitos)
        self.vigiada.pela_porta = frozenset(
            sup.pastas_pela_porta(self.manifesto, self.vigiada.aceitos).values())
        self.caixa = _caixa_no_hub(self.hub, self.e429, self.vigiada.retrato, self.vigiada.hid,
                                   fecha=self.fecha, por_fora=self.por_fora)
        self.vigiada.processo = self.caixa  # type: ignore[assignment]

    def fechar(self) -> None:
        if self.caixa is not None:
            self.caixa.kill()
            self.caixa.communicate(timeout=60)
            self.caixa = None

    def volta(self, pedido: str = "") -> dict[str, Any]:
        asyncio.run(self.supervisor._conferir_os_aparelhos())
        assert self.caixa is not None
        return _ver(self.caixa, pedido)


@pytest.mark.parametrize(("cascata", "por_fora"), [
    ("3-1", False), ("3-1/3-1.1", False), ("3-1", True)])
def test_a_vigia_cobre_o_irmao_por_dentro_sem_reabrir(
        curto: Path, monkeypatch: pytest.MonkeyPatch, cascata: str, por_fora: bool) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: no hub do adaptador (também o segundo hub
    da cascata, e com a caixa dentro de outro espaço de PID, como no ``pasta``), liga A, liga B,
    tira A, religa A, o rádio sai e volta e o adaptador faz quatro RESET;: a caixa nunca mostra
    irmão nem endereço, a pasta do HID segue o rádio, e nada reabre."""
    vigia = _Vigia(curto, cascata, monkeypatch, por_fora=por_fora)
    nome = vigia.hub.name
    try:
        visto = vigia.volta()
        assert (visto["hid"], visto["hidraw"]) == (
            ["0003:1A86:E429.0007", f"0005:054C:0CE6.0002-{nome}.2"], ["hidraw7"])
        for numero in range(8, 12):
            vigia.ligar(numero)
            assert vigia.volta()["hidraw"] == [f"hidraw{numero}"]
        passos = [lambda: _irmao(vigia.hub, f"{nome}.1", "0003:054C:0CE6.0010", vigia.bus),
                  lambda: _irmao(vigia.hub, f"{nome}.3", "0003:054C:0CE6.0011", vigia.bus),
                  lambda: shutil.rmtree(vigia.hub / f"{nome}.1"),
                  lambda: _irmao(vigia.hub, f"{nome}.1", "0003:054C:0CE6.0012", vigia.bus),
                  lambda: _irmao(vigia.hub, f"{nome}.2", "0005:054C:0CE6.0013", vigia.bus)]
        for passo in passos:
            passo()
            visto = vigia.volta()
            assert (visto["vizinhos"], visto["uniq"], visto["hidraw"]) == ([], 0, ["hidraw11"])
        assert visto["hid"] == ["0003:1A86:E429.0011", f"0005:054C:0CE6.0013-{nome}.2"]
        assert vigia.reabertas == [], "cobrir por dentro não reabre a caixa"
    finally:
        vigia.fechar()


class _Diario:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, _nivel: str) -> Any:
        return lambda evento, **campos: self.linhas.append((evento, campos))


@pytest.mark.parametrize(("como", "motivo"), [
    ("fugir", "escape"), ("hub", "hub_saiu"), ("falha", "cobertura_falhou")])
def test_a_caixa_reabre_quando_a_cobertura_nao_vale_e_diz_por_que(
        curto: Path, monkeypatch: pytest.MonkeyPatch, como: str, motivo: str) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: a caixa reabre, com o motivo no diário do
    serviço, quando um processo da caixa mora noutro espaço de montagem (o bwrap sem
    --disable-userns), quando o hub sai e quando a mudança por dentro falha; a nova caixa não
    mostra o irmão."""
    vigia = _Vigia(curto, "3-1", monkeypatch, fecha=como != "fugir")
    diario = _Diario()
    monkeypatch.setattr(sup, "logger", diario)
    try:
        vigia.volta()
        assert vigia.caixa is not None
        if como == "fugir":
            _ver(vigia.caixa, "fugir")
        if como == "falha":
            monkeypatch.setattr(sup, "POR_DENTRO_DA_CAIXA", curto / "nao-existe.py")
        _irmao(vigia.hub, "3-1.3", "0003:054C:0CE6.0020", vigia.bus)
        if como == "hub":
            shutil.rmtree(vigia.hub)
            asyncio.run(vigia.supervisor._conferir_os_aparelhos())
        else:
            visto = vigia.volta()
            assert (visto["vizinhos"], visto["uniq"]) == ([], 0), visto
        assert vigia.reabertas == ["exemplo"], como
        assert ("mods_caixa_reabre", {"mod": "exemplo", "motivo": motivo}) in diario.linhas
    finally:
        vigia.fechar()


_TENTA_O_USERNS = r"""
import os
try:
    os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNS)
    print('abriu')
except OSError as exc:
    print(exc.errno)
"""


def test_a_caixa_nasce_sem_poder_abrir_espaco_de_usuario(curto: Path) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: pela linha do produto, com o bwrap que
    aceita --disable-userns, a extensão não abre espaço de usuário (nem de montagem) próprio."""
    exigir_caixa_do_bwrap()
    bwrap = shutil.which("bwrap") or "bwrap"
    if not sup.bwrap_fecha_o_userns(bwrap):
        pytest.skip("o bwrap desta máquina não aceita --disable-userns")
    for pedidas in (("aparelhos", "bluetooth", "rede:internet"), ("rede:nenhuma",)):
        fonte, dados, casa = (curto / f"{p}-{len(pedidas)}" for p in ("fonte", "dados", "casa"))
        for pasta in (fonte, dados, casa):
            pasta.mkdir()
        argv = sup.comando_na_caixa(
            bwrap=bwrap, comando=[sys.executable, "-c", _TENTA_O_USERNS], codigo=fonte,
            dados=dados, porta=curto / "porta.sock", manifesto=_manifesto(*pedidas), casa=casa,
            execucao=())
        (curto / "porta.sock").touch()
        feito = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
        assert feito.stdout.strip() != "abriu", pedidas
        assert feito.returncode == 0, feito.stderr[-300:]
        assert "--disable-userns" in argv[:argv.index("--")]


def test_o_uevent_do_aparelho_usb_acorda_a_vigia_na_hora(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: o aparelho USB que entra acorda a vigia
    pelo uevent, sem esperar a volta; a interface USB não acorda."""
    from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb

    de_fora, do_kernel = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    monkeypatch.setattr(ouvido_do_usb, "abrir_o_netlink", lambda: do_kernel)
    supervisor = sup.Supervisor.__new__(sup.Supervisor)
    acordou: list[str] = []

    async def conferir() -> None:
        acordou.append("vigia")

    supervisor._conferir_os_aparelhos = conferir  # type: ignore[method-assign]

    async def rodar() -> None:
        ouvido = asyncio.create_task(supervisor._ouvir_o_barramento())
        de_fora.send(b"add@/devices/usb3/3-1/3-1:1.0\0ACTION=add\0SUBSYSTEM=usb\0"
                     b"DEVTYPE=usb_interface\0")
        de_fora.send(b"add@/devices/usb3/3-1/3-1.3\0ACTION=add\0SUBSYSTEM=usb\0"
                     b"DEVTYPE=usb_device\0")
        for _ in range(100):
            if acordou:
                break
            await asyncio.sleep(0.01)
        ouvido.cancel()
        await asyncio.gather(ouvido, return_exceptions=True)

    do_kernel.setblocking(False)
    asyncio.run(rodar())
    de_fora.close()
    assert acordou == ["vigia"]
