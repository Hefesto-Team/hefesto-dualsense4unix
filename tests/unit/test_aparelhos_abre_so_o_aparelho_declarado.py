"""A permissão ``aparelhos`` abre só o aparelho declarado.

Sprint APARELHOS-ABRE-SO-O-APARELHO-DECLARADO-01.

O manifesto declara a classe (``hidraw``, ``tty``, ``usb``) e o VID:PID; a caixa fica com o ``/dev``
mínimo do ``bwrap`` e recebe só os nós que casam. O ``uinput``, o ``uhid`` e o ``input/`` nunca
entram, nem o controle e o teclado. O aparelho que entra depois da abertura reabre a caixa.

O declarado ``pela_porta`` (o adaptador 1a86:e429, que volta do ``RESET;`` com outro hidraw) nunca
entra na caixa nem a reabre: a extensão pede o nó à porta (``aparelho.abrir``) e recebe o fd.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto

__all__ = ["curto"]

_ADAPTADOR = {"classe": "hidraw", "vid": "1a86", "pid": "e429", "nome": "o adaptador USB"}


def _manifesto(permissoes: list[str], aparelhos: list[dict[str, Any]] | None = None) -> Manifesto:
    bruto: dict[str, Any] = {
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": permissoes,  # (noqa-acento)
    }
    if aparelhos is not None:
        bruto["aparelhos"] = aparelhos
    return Manifesto.model_validate(bruto)


def _caixa(base: Path, manifesto: Manifesto, comando: list[str],
           aparelhos: tuple[str, ...] = ()) -> list[str]:
    fonte, dados, casa = base / "fonte", base / "dados", base / "casa"
    for pasta in (fonte, dados, casa):
        pasta.mkdir(exist_ok=True)
    porta = base / "porta.sock"
    porta.touch()
    return sup.comando_na_caixa(bwrap=shutil.which("bwrap") or "bwrap", comando=comando,
                                codigo=fonte, dados=dados, porta=porta, manifesto=manifesto,
                                casa=casa, execucao=(), aparelhos=aparelhos)


def _sys_de_mentira(raiz: Path) -> Path:
    """Um ``/sys`` com o adaptador (hidraw e tty), o controle, o teclado e um USB cru."""
    sys_ = raiz / "sys"

    def usb(nome: str, vid: str, pid: str, bus: int, dev: int) -> Path:
        pasta = sys_ / "devices/pci0000:00/usb3" / nome
        pasta.mkdir(parents=True)
        for arquivo, valor in (("idVendor", vid), ("idProduct", pid),
                               ("busnum", str(bus)), ("devnum", str(dev))):
            (pasta / arquivo).write_text(valor + "\n")
        (sys_ / "bus/usb/devices").mkdir(parents=True, exist_ok=True)
        (sys_ / "bus/usb/devices" / nome).symlink_to(pasta)
        return pasta

    def hidraw(no: str, hid_id: str) -> None:
        dispositivo = sys_ / "devices/hid" / no
        dispositivo.mkdir(parents=True)
        (dispositivo / "uevent").write_text(f"DRIVER=hid-generic\nHID_ID={hid_id}\n")
        classe = sys_ / "class/hidraw" / no
        classe.mkdir(parents=True)
        (classe / "device").symlink_to(dispositivo)

    adaptador = usb("3-1", "1a86", "e429", 3, 7)
    usb("3-2", "054c", "0ce6", 3, 8)
    hidraw("hidraw3", "0003:00001A86:0000E429")
    hidraw("hidraw4", "0003:0000054C:00000CE6")
    hidraw("hidraw5", "0005:0000046D:0000C52B")
    interface = adaptador / "3-1:1.0"
    interface.mkdir()
    tty = sys_ / "class/tty/ttyACM0"
    tty.mkdir(parents=True)
    (tty / "device").symlink_to(interface)
    (sys_ / "class/tty/tty0").mkdir()
    return sys_


def test_so_os_nos_do_aparelho_declarado_casam(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    so_hid = _manifesto(["aparelhos"], [_ADAPTADOR])
    assert sup.aparelhos_que_casam(so_hid, sys_) == ("/dev/hidraw3",)
    tudo = _manifesto(["aparelhos"], [
        _ADAPTADOR, {**_ADAPTADOR, "classe": "tty"}, {**_ADAPTADOR, "classe": "usb"}])
    assert sup.aparelhos_que_casam(tudo, sys_) == (
        "/dev/hidraw3", "/dev/ttyACM0", "/dev/bus/usb/003/007")
    assert sup.aparelhos_que_casam(_manifesto(["aparelhos"]), sys_) == ()
    assert sup.aparelhos_que_casam(_manifesto([]), sys_) == ()


def test_a_linha_tem_o_dev_minimo_e_so_o_no_declarado(curto: Path) -> None:
    argv = _caixa(curto, _manifesto(["aparelhos"], [_ADAPTADOR]), ["true"],
                  aparelhos=("/dev/hidraw3", "/dev/uinput", "/dev/uhid", "/dev/input/event3",
                             "/dev/hidraw/../uinput"))
    fim = argv.index("--")
    assert "/dev/uinput" not in argv[:fim] and "/dev/uhid" not in argv[:fim]
    assert not any("input" in a for a in argv[:fim])
    assert ["--dev-bind", "/dev", "/dev"] not in [argv[i:i + 3] for i in range(fim)]
    assert argv[argv.index("--dev") + 1] == "/dev"
    i = argv.index("--dev-bind-try")
    assert argv[i:i + 3] == ["--dev-bind-try", "/dev/hidraw3", "/dev/hidraw3"]
    assert argv.count("--dev-bind-try") == 1


def test_sem_a_permissao_nenhum_no_entra(curto: Path) -> None:
    argv = _caixa(curto, _manifesto([]), ["true"], aparelhos=("/dev/hidraw3",))
    assert "--dev-bind-try" not in argv and "/dev/hidraw3" not in argv


@pytest.mark.parametrize("aparelho, motivo", [
    ({**_ADAPTADOR, "classe": "input"}, "classe"),
    ({**_ADAPTADOR, "vid": "1A86"}, "hexadecimais"),
    ({**_ADAPTADOR, "pid": "e42"}, "hexadecimais"),
    ({k: v for k, v in _ADAPTADOR.items() if k != "nome"}, "nome"),
    ({**_ADAPTADOR, "caminho": "/dev/uinput"}, "caminho"),
])
def test_a_forma_dos_aparelhos_e_conferida(aparelho: dict[str, Any], motivo: str) -> None:
    with pytest.raises(ValueError, match=motivo):
        _manifesto(["aparelhos"], [aparelho])


def test_a_lista_pede_a_permissao_e_nao_repete() -> None:
    with pytest.raises(ValueError, match="pede a permissão aparelhos"):
        _manifesto([], [_ADAPTADOR])
    with pytest.raises(ValueError, match="repetido"):
        _manifesto(["aparelhos"], [_ADAPTADOR, {**_ADAPTADOR, "nome": "outro"}])


def test_o_sim_lista_os_aparelhos_pelo_nome() -> None:
    frase = sup.frase_dos_aparelhos(_manifesto(["aparelhos"], [
        _ADAPTADOR, {**_ADAPTADOR, "classe": "tty"}]))
    assert frase.endswith("só: o adaptador USB."), frase
    assert "não abre aparelho nenhum" in sup.frase_dos_aparelhos(_manifesto(["aparelhos"]))
    assert sup.frase_dos_aparelhos(_manifesto([])) == ""


_SONDA = """
import os, sys
for caminho in sys.argv[1:]:
    try:
        os.close(os.open(caminho, os.O_RDWR))
        print(caminho, "abriu")
    except OSError as exc:
        print(caminho, type(exc).__name__)
print("hidraw", sorted(n for n in os.listdir("/dev") if n.startswith("hidraw")))
print("input", os.path.exists("/dev/input"))
"""


def test_com_o_bwrap_real_o_uinput_nao_abre_de_dentro(curto: Path) -> None:
    exigir_caixa_do_bwrap()
    reais = sorted(f"/dev/{n}" for n in os.listdir("/dev") if n.startswith("hidraw"))
    declarado = tuple(reais[:1])
    feito = subprocess.run(
        _caixa(curto, _manifesto(["aparelhos"], [_ADAPTADOR]),
               ["/usr/bin/python3", "-c", _SONDA, "/dev/uinput", "/dev/uhid"],
               aparelhos=declarado),
        capture_output=True, text=True, timeout=60, check=False)
    assert feito.returncode == 0, feito.stderr
    visto = dict(linha.split(" ", 1) for linha in feito.stdout.splitlines())
    assert visto["/dev/uinput"] == "FileNotFoundError", visto
    assert visto["/dev/uhid"] == "FileNotFoundError", visto
    assert visto["input"] == "False", visto
    assert visto["hidraw"] == str([p.removeprefix("/dev/") for p in declarado]), visto


def test_o_aparelho_que_entra_depois_reabre_a_caixa(monkeypatch: pytest.MonkeyPatch) -> None:
    manifesto = _manifesto(["aparelhos"], [_ADAPTADOR])
    ligados: list[tuple[str, ...]] = [("/dev/hidraw3",)]
    monkeypatch.setattr(sup, "aparelhos_que_casam", lambda m, *a: ligados[-1])

    class Processo:
        returncode = None

    reabertas: list[str] = []
    supervisor = sup.Supervisor.__new__(sup.Supervisor)
    supervisor.bwrap = "/usr/bin/bwrap"
    supervisor._registro_lido = {"exemplo": object()}  # type: ignore[dict-item]
    supervisor._reaberta_pelo_aparelho = {}
    vigiada = sup._Vigiada("exemplo", processo=Processo(),  # type: ignore[arg-type]
                           manifesto=manifesto, aparelhos=("/dev/hidraw3",))
    supervisor._vigiadas = {"exemplo": vigiada}

    async def comecar(entrada: Any) -> None:
        reabertas.append("exemplo")

    supervisor._comecar = comecar  # type: ignore[method-assign]

    async def voltas(n: int) -> None:
        for _ in range(n):
            await supervisor._conferir_os_aparelhos()

    ligados.append(())
    asyncio.run(voltas(3))
    ligados.append(("/dev/hidraw3",))
    asyncio.run(voltas(3))
    assert reabertas == [], "o adaptador que sai e volta no mesmo nó não reabre a caixa"
    ligados.append(("/dev/hidraw3", "/dev/hidraw9"))
    asyncio.run(voltas(1))
    assert reabertas == [], "uma volta só com o nó novo ainda espera"
    asyncio.run(voltas(1))
    assert reabertas == ["exemplo"]


_PELA_PORTA = {**_ADAPTADOR, "pela_porta": True}
_NULO = os.stat("/dev/null").st_rdev
_ZERO = os.stat("/dev/zero").st_rdev


def _no_de_mentira(sys_: Path, dev: Path, no: str, hid_id: str, alvo: str = "/dev/null") -> None:
    """Um hidraw no ``/sys`` com o número do ``/dev/null``; no ``dev``, o nó leva a ``alvo``."""
    dispositivo = sys_ / "devices/hid" / no
    dispositivo.mkdir(parents=True, exist_ok=True)
    (dispositivo / "uevent").write_text(f"DRIVER=hid-generic\nHID_ID={hid_id}\n")
    classe = sys_ / "class/hidraw" / no
    classe.mkdir(parents=True, exist_ok=True)
    (classe / "dev").write_text(f"{os.major(_NULO)}:{os.minor(_NULO)}\n")
    if not (classe / "device").is_symlink():
        (classe / "device").symlink_to(dispositivo)
    dev.mkdir(exist_ok=True)
    (dev / no).unlink(missing_ok=True)
    (dev / no).symlink_to(alvo)


def _renascer(sys_: Path, dev: Path, de: str, para: str) -> None:
    """O ``RESET;``: o hidraw ``de`` some e o mesmo adaptador volta como ``para``."""
    shutil.rmtree(sys_ / "class/hidraw" / de)
    (dev / de).unlink()
    _no_de_mentira(sys_, dev, para, "0003:00001A86:0000E429")


def test_o_declarado_pela_porta_nunca_entra_na_caixa(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    assert sup.aparelhos_que_casam(_manifesto(["aparelhos"], [_PELA_PORTA]), sys_) == ()
    misto = _manifesto(["aparelhos"], [_PELA_PORTA, {**_ADAPTADOR, "classe": "tty"}])
    assert sup.aparelhos_que_casam(misto, sys_) == ("/dev/ttyACM0",)


def test_abrir_o_aparelho_confere_o_sys_e_o_numero_do_no(tmp_path: Path) -> None:
    sys_, dev = _sys_de_mentira(tmp_path), tmp_path / "dev"
    _no_de_mentira(sys_, dev, "hidraw3", "0003:00001A86:0000E429")
    _no_de_mentira(sys_, dev, "hidraw4", "0003:0000054C:00000CE6")
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    fd = sup.abrir_o_aparelho(manifesto, "hidraw3", sys_, dev)
    try:
        assert os.fstat(fd).st_rdev == _NULO
    finally:
        os.close(fd)
    for torto in ("hidraw4", "hidraw/../uinput", "/dev/hidraw3", "", 7, None, "uinput"):
        with pytest.raises(ValueError, match=r"aparelho\.abrir"):
            sup.abrir_o_aparelho(manifesto, torto, sys_, dev)
    with pytest.raises(ValueError, match=r"aparelho\.abrir"):
        sup.abrir_o_aparelho(_manifesto([]), "hidraw3", sys_, dev)
    _no_de_mentira(sys_, dev, "hidraw3", "0003:00001A86:0000E429", alvo="/dev/zero")
    with pytest.raises(ValueError, match="mudou de aparelho"):
        sup.abrir_o_aparelho(manifesto, "hidraw3", sys_, dev)


def _pedir_o_fd(caminho: Path, pedido: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(str(caminho))
        sock.sendall((json.dumps(pedido) + "\n").encode())
        cru, fds, _, _ = socket.recv_fds(sock, 65536, 1)
        assert sock.recv(1) == b"", "a conexão do aparelho fecha depois da resposta"
    return json.loads(cru), fds


def _abrir(no: str, ficha: str = "ficha") -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "method": "aparelho.abrir",
            "params": {"ficha": ficha, "no": no}}


async def _porta_com_o_aparelho(pasta: Path, manifesto: Manifesto, sys_: Path, dev: Path,
                                pid: int) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(pasta / "porta.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: None)
    await porta.iniciar()
    porta.registrar("ficha", "exemplo", pid, manifesto.permissoes,
                    abrir_o_aparelho=lambda no: sup.abrir_o_aparelho(manifesto, no, sys_, dev))
    return porta


def test_o_no_que_renasce_se_pede_de_novo_pela_porta(curto: Path) -> None:
    sys_, dev = _sys_de_mentira(curto), curto / "dev"
    _no_de_mentira(sys_, dev, "hidraw3", "0003:00001A86:0000E429")
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])

    async def cena() -> None:
        porta = await _porta_com_o_aparelho(curto, manifesto, sys_, dev, os.getpid())
        try:
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("hidraw3"))
            assert resposta["result"] == {"no": "hidraw3"} and len(fds) == 1, resposta
            assert os.fstat(fds[0]).st_rdev == _NULO
            os.close(fds[0])
            _renascer(sys_, dev, "hidraw3", "hidraw9")
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("hidraw3"))
            assert "error" in resposta and fds == [], "o nó que sumiu não abre mais"
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("hidraw9"))
            assert resposta["result"] == {"no": "hidraw9"} and len(fds) == 1, resposta
            assert os.write(fds[0], b"RESET;\r\n") == 8
            os.close(fds[0])
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho,
                                                    _abrir("hidraw9", "outra"))
            assert resposta["error"]["message"] == "ficha desconhecida" and fds == []
        finally:
            await porta.parar()

    asyncio.run(cena())


def test_sem_aparelho_declarado_a_porta_nao_entrega_fd(curto: Path) -> None:
    async def cena() -> None:
        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            return {"status": "ok"}

        porta = Porta(curto / "porta.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: None)
        await porta.iniciar()
        porta.registrar("ficha", "exemplo", os.getpid(), ["aparelhos"])
        try:
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("hidraw3"))
            assert resposta["error"]["code"] == CODE_SEM_PERMISSAO and fds == [], resposta
        finally:
            await porta.parar()

    asyncio.run(cena())


def test_o_aparelho_abrir_so_vale_como_primeira_palavra(curto: Path) -> None:
    sys_, dev = _sys_de_mentira(curto), curto / "dev"
    _no_de_mentira(sys_, dev, "hidraw3", "0003:00001A86:0000E429")
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])

    def depois_do_ola(caminho: Path) -> tuple[dict[str, Any], list[int]]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(str(caminho))
            ola = {"jsonrpc": "2.0", "id": 0, "method": "mod.ola", "params": {"ficha": "ficha"}}
            sock.sendall((json.dumps(ola) + "\n" + json.dumps(_abrir("hidraw3")) + "\n").encode())
            lido, fds = b"", []
            while lido.count(b"\n") < 2:
                cru, novos, _, _ = socket.recv_fds(sock, 65536, 1)
                lido, fds = lido + cru, fds + novos
        return json.loads(lido.splitlines()[1]), fds

    async def cena() -> None:
        porta = await _porta_com_o_aparelho(curto, manifesto, sys_, dev, os.getpid())
        try:
            resposta, fds = await asyncio.to_thread(depois_do_ola, porta.caminho)
            assert "desconhecido" in resposta["error"]["message"] and fds == [], resposta
        finally:
            await porta.parar()

    asyncio.run(cena())


_NA_CAIXA = """
import json, os, socket, sys, time
caminho, no = sys.argv[1], sys.argv[2]
print("no_na_caixa", os.path.exists("/dev/" + no))
for _ in range(50):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(caminho)
        pedido = {"jsonrpc": "2.0", "id": 1, "method": "aparelho.abrir",
                  "params": {"ficha": "ficha", "no": no}}
        sock.sendall((json.dumps(pedido) + "\\n").encode())
        cru, fds, _, _ = socket.recv_fds(sock, 65536, 1)
    resposta = json.loads(cru)
    if fds:
        break
    time.sleep(0.1)
print("resposta", json.dumps(resposta))
print("rdev", os.fstat(fds[0]).st_rdev if fds else None)
print("escreveu", os.write(fds[0], b"DeviceType;\\r\\n") if fds else None)
"""


def test_com_o_bwrap_real_o_no_que_renasce_chega_pela_porta(curto: Path) -> None:
    """D-1511-O-APARELHO-QUE-RENASCE-VEM-PELA-PORTA."""
    exigir_caixa_do_bwrap()
    sys_, dev = _sys_de_mentira(curto), curto / "dev"
    _no_de_mentira(sys_, dev, "hidraw3", "0003:00001A86:0000E429")
    _renascer(sys_, dev, "hidraw3", "hidraw9")
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])

    async def cena() -> str:
        porta = await _porta_com_o_aparelho(curto, manifesto, sys_, dev, -1)
        argv = _caixa(curto, manifesto, ["/usr/bin/python3", "-I", "-c", _NA_CAIXA,
                                         str(porta.caminho), "hidraw9"],
                      aparelhos=sup.aparelhos_que_casam(manifesto, sys_))
        assert not any("hidraw" in a for a in argv[:argv.index("--")])
        processo = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        porta.registrar("ficha", "exemplo", processo.pid, manifesto.permissoes,
                        abrir_o_aparelho=lambda no: sup.abrir_o_aparelho(manifesto, no, sys_, dev))
        try:
            saida, _ = await asyncio.wait_for(processo.communicate(), timeout=60)
        finally:
            await porta.parar()
        return saida.decode()

    saida = asyncio.run(cena())
    visto = dict(linha.split(" ", 1) for linha in saida.splitlines() if " " in linha)
    assert visto.get("no_na_caixa") == "False", saida
    assert json.loads(visto["resposta"]).get("result") == {"no": "hidraw9"}, saida
    assert visto["rdev"] == str(_NULO), saida
    assert visto["escreveu"] == "13", saida


def _vigia_de_mentira(manifesto: Manifesto, aparelhos: tuple[str, ...]
                      ) -> tuple[sup.Supervisor, sup._Vigiada, list[str]]:
    class Processo:
        returncode = None

    reabertas: list[str] = []
    supervisor = sup.Supervisor.__new__(sup.Supervisor)
    supervisor.bwrap = "/usr/bin/bwrap"
    supervisor._registro_lido = {"exemplo": object()}  # type: ignore[dict-item]
    supervisor._reaberta_pelo_aparelho = {}
    vigiada = sup._Vigiada("exemplo", processo=Processo(),  # type: ignore[arg-type]
                           manifesto=manifesto, aparelhos=aparelhos)
    supervisor._vigiadas = {"exemplo": vigiada}

    async def comecar(entrada: Any) -> None:
        reabertas.append("exemplo")
        vigiada.aparelhos = sup.aparelhos_que_casam(manifesto)
        vigiada.aparelho_novo = False

    supervisor._comecar = comecar  # type: ignore[method-assign]
    return supervisor, vigiada, reabertas


def test_o_reset_do_adaptador_pela_porta_nunca_reabre_a_caixa(
        curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys_, dev = _sys_de_mentira(curto), curto / "dev"
    real = sup.aparelhos_que_casam
    monkeypatch.setattr(sup, "aparelhos_que_casam", lambda m, *a: real(m, sys_))
    _no_de_mentira(sys_, dev, "hidraw3", "0003:00001A86:0000E429")
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    supervisor, _vigiada, reabertas = _vigia_de_mentira(manifesto, ())

    async def resets() -> None:
        atual = "hidraw3"
        for numero in range(10, 16):
            _renascer(sys_, dev, atual, f"hidraw{numero}")
            atual = f"hidraw{numero}"
            for _ in range(3):
                await supervisor._conferir_os_aparelhos()

    asyncio.run(resets())
    assert reabertas == [], "o adaptador que volta do RESET; com outro hidraw não reabre a caixa"


def test_o_no_que_renasce_a_cada_abertura_reabre_uma_vez_e_para(
        monkeypatch: pytest.MonkeyPatch) -> None:
    manifesto = _manifesto(["aparelhos"], [_ADAPTADOR])
    contador = iter(range(10, 100))
    monkeypatch.setattr(sup, "aparelhos_que_casam", lambda m, *a: (f"/dev/hidraw{next(contador)}",))
    supervisor, vigiada, reabertas = _vigia_de_mentira(manifesto, ("/dev/hidraw3",))

    async def voltas(n: int) -> None:
        for _ in range(n):
            await supervisor._conferir_os_aparelhos()

    asyncio.run(voltas(12))
    assert reabertas == ["exemplo"], "a segunda reabertura dentro da janela vira laço e não sai"
    assert vigiada.aparelho_em_laco
