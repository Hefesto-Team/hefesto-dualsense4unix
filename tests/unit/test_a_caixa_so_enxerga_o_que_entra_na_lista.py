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
import glob, json, os, sys
hub, e429 = sys.argv[1], sys.argv[2]
def ler(p):
    try:
        with open(p, 'rb') as f:
            return f.read()
    except OSError:
        return b''
for _ in sys.stdin:
    uniq = sum(l.startswith(b'HID_UNIQ=02:fe') for u in glob.glob('/sys/bus/hid/devices/*/uevent')
               for l in ler(u).splitlines())
    print(json.dumps({
        'vizinhos': sorted(f for f in os.listdir(hub)
                         if os.path.join(hub, f) != e429 and ler(os.path.join(hub, f, 'idVendor'))),
        'uniq': uniq,
        'hidraw': sorted(os.path.basename(p) for p in glob.glob(e429 + '/*/*/hidraw/*'))}),
        flush=True)
"""


def test_o_irmao_que_o_hub_vivo_mostra_entra_na_vigia_e_a_nova_caixa_o_cobre(curto: Path) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: o controle ligado depois e o coberto que
    sai e volta aparecem pelo hub vivo (com o endereço pelo link do HID); a vigia os acha, a caixa
    nova os cobre, e quatro RESET; seguidos do adaptador nunca entram na vigia."""
    exigir_caixa_do_bwrap()
    hub = curto / "sys" / "devices" / "usb3" / "3-1"
    bus = curto / "bus-hid"
    bus.mkdir()
    _irmao(hub, "3-1.2", "0003:054C:0CE6.0002", bus)

    def abrir(retrato: sup.RetratoDosHubs) -> subprocess.Popen[str]:
        real = next(hub.glob("3-1.4/*/*/hidraw/*"))
        argv = [shutil.which("bwrap") or "bwrap", *sup._o_que_entra(sup.ENTRAM_NA_CAIXA),
                "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/sys",
                *sup._o_sys_dos_achados([("/sys/dev/char/240:7", str(real))], retrato),
                "--ro-bind", str(bus), "/sys/bus/hid/devices"]
        comando = sup._executavel_a_vista(
            [sys.executable, "-c", _OLHA_OS_IRMAOS, str(hub), str(hub / "3-1.4")],
            sup.ENTRAM_NA_CAIXA, argv)
        return subprocess.Popen([*argv, "--", *comando], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def ver(caixa: subprocess.Popen[str]) -> dict[str, object]:
        assert caixa.stdin is not None and caixa.stdout is not None
        caixa.stdin.write("\n")
        caixa.stdin.flush()
        linha = caixa.stdout.readline()
        assert linha, caixa.stderr.read()[-400:] if caixa.stderr else ""
        visto: dict[str, object] = json.loads(linha)
        return visto

    _usb(hub, "3-1.4", "0003:1A86:E429.0001", "hidraw7")
    retrato: sup.RetratoDosHubs = {}
    with abrir(retrato) as caixa:
        assert ver(caixa) == {"vizinhos": [], "uniq": 0, "hidraw": ["hidraw7"]}
        _irmao(hub, "3-1.3", "0003:054C:0CE6.0003", bus)
        _irmao(hub, "3-1.2", "0003:054C:0CE6.0004", bus)
        assert ver(caixa) == {"vizinhos": ["3-1.2", "3-1.3"], "uniq": 2, "hidraw": ["hidraw7"]}
        assert sup.irmaos_a_vista(retrato) == [str(hub / "3-1.2"), str(hub / "3-1.3")]
        caixa.communicate("", timeout=60)
    retrato = {}
    with abrir(retrato) as caixa:
        assert ver(caixa) == {"vizinhos": [], "uniq": 0, "hidraw": ["hidraw7"]}
        for numero in range(8, 12):
            shutil.rmtree(hub / "3-1.4")
            _usb(hub, "3-1.4", f"0003:1A86:E429.{numero:04d}", f"hidraw{numero}")
            assert sup.irmaos_a_vista(retrato) == [], "o RESET; na mesma porta não reabre"
            assert ver(caixa) == {"vizinhos": [], "uniq": 0, "hidraw": [f"hidraw{numero}"]}
        caixa.communicate("", timeout=60)


def _hub_com_o_adaptador(sys_: Path, hub: Path) -> tuple[Path, Path]:
    bus = sys_ / "bus-hid"
    bus.mkdir(parents=True)
    _irmao(hub, f"{hub.name}.2", "0003:054C:0CE6.0002", bus)
    (sys_ / "class" / "hidraw").mkdir(parents=True)
    return bus, hub / f"{hub.name}.4"


@pytest.mark.parametrize("cascata", ["3-1", "3-1/3-1.1"])
def test_a_vigia_reabre_pelo_irmao_e_nunca_pelo_reset(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cascata: str) -> None:
    """D-1911-A-CAIXA-SO-ENXERGA-O-QUE-ENTRA-NA-LISTA: no hub do adaptador (também o segundo hub
    da cascata), o irmão ligado depois e o que sai e volta reabrem a caixa na primeira volta,
    também com a vigia do aparelho em laço; o hub que sai, uma vez; quatro RESET; seguidos,
    nenhuma."""
    sys_ = tmp_path / "sys"
    hub = sys_ / "devices" / "usb3" / cascata
    bus, e429 = _hub_com_o_adaptador(sys_, hub)

    def ligar(numero: int) -> None:
        if e429.exists():
            shutil.rmtree(e429)
            for velho in (sys_ / "class" / "hidraw").iterdir():
                velho.unlink()
        no = _usb(hub, e429.name, f"0003:1A86:E429.{numero:04d}", f"hidraw{numero}")
        (sys_ / "class" / "hidraw" / f"hidraw{numero}").symlink_to(no)

    ligar(7)
    manifesto = _manifesto("aparelhos", aparelhos=(_E429,))
    supervisor, reabertas = _vigia(manifesto, sys_, monkeypatch)
    vigiada = supervisor._vigiadas["exemplo"]

    def retratar() -> None:
        vigiada.retrato = {}
        for real in e429.glob("*/*/hidraw/*"):
            sup._o_sys_dos_achados([("/sys/dev/char/240:7", str(real))], vigiada.retrato)

    comecar = supervisor._comecar

    async def comecar_e_retratar(entrada: object) -> None:
        await comecar(entrada)
        retratar()

    supervisor._comecar = comecar_e_retratar  # type: ignore[method-assign]
    retratar()

    def voltas(n: int) -> None:
        async def rodar() -> None:
            for _ in range(n):
                await supervisor._conferir_os_aparelhos()
        asyncio.run(rodar())

    voltas(3)
    for numero in range(8, 12):
        ligar(numero)
        voltas(3)
    assert reabertas == [], "o RESET; na mesma porta não reabre a caixa"
    _irmao(hub, f"{hub.name}.3", "0003:054C:0CE6.0003", bus)
    voltas(1)
    assert reabertas == ["exemplo"], "o irmão ligado depois reabre na primeira volta"
    _irmao(hub, f"{hub.name}.2", "0003:054C:0CE6.0004", bus)
    vigiada.aparelho_em_laco = True
    voltas(1)
    assert reabertas == ["exemplo"] * 2, "o coberto que sai e volta reabre, também em laço"
    voltas(3)
    assert reabertas == ["exemplo"] * 2
    shutil.rmtree(hub)
    voltas(3)
    assert reabertas == ["exemplo"] * 3, "o hub que sai leva a montagem: a caixa reabre"
    assert sup.irmaos_a_vista({}) == []
