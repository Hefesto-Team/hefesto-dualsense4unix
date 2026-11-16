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
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto, aparelhos_do_sim
from hefesto_dualsense4unix.mods.porta import (
    APARELHOS_POR_SEGUNDO,
    CODE_SEM_PERMISSAO,
    CODE_TETO_CHEIO,
    Porta,
)
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto

__all__ = ["curto"]

_ADAPTADOR = {"classe": "hidraw", "vid": "1a86", "pid": "e429", "nome": "o adaptador USB"}
_DA_FABRICANTE = bytes.fromhex("06a0ff0901a101090115002 6ff00750895408102c0".replace(" ", ""))


def _aceitos(manifesto: Manifesto) -> list[str]:
    return aparelhos_do_sim(manifesto)


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
        (dispositivo / "report_descriptor").write_bytes(_DA_FABRICANTE)
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
    assert sup.aparelhos_que_casam(so_hid, _aceitos(so_hid), sys_) == ("/dev/hidraw3",)
    tudo = _manifesto(["aparelhos"], [
        _ADAPTADOR, {**_ADAPTADOR, "classe": "tty"}, {**_ADAPTADOR, "classe": "usb"}])
    assert sup.aparelhos_que_casam(tudo, _aceitos(tudo), sys_) == (
        "/dev/hidraw3", "/dev/ttyACM0", "/dev/bus/usb/003/007")
    for vazio in (_manifesto(["aparelhos"]), _manifesto([])):
        assert sup.aparelhos_que_casam(vazio, _aceitos(vazio), sys_) == ()
    assert sup.aparelhos_que_casam(tudo, [], sys_) == (), "sem o «sim» do aparelho, nada entra"


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


def test_o_sim_lista_os_aparelhos_pelo_nome(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    frase = sup.frase_dos_aparelhos(_manifesto(["aparelhos"], [
        _ADAPTADOR, {**_ADAPTADOR, "classe": "tty"}]), sys_, ler_o_usb=False)
    assert frase.endswith("só: «o adaptador USB» (hidraw 1a86:e429); «o adaptador USB» (tty "
                          "1a86:e429)."), frase
    assert "não abre aparelho nenhum" in sup.frase_dos_aparelhos(_manifesto(["aparelhos"]), sys_)
    assert sup.frase_dos_aparelhos(_manifesto([]), sys_) == ""


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
_SO_PORTA = _manifesto(["aparelhos"], [_PELA_PORTA])
_E429 = "0003:00001A86:0000E429"
_DUALSENSE = "0003:0000054C:00000CE6"
_DEV = Path("/dev")
_NULO = os.stat("/dev/null").st_rdev
_ZERO = os.stat("/dev/zero").st_rdev


def _no_de_mentira(sys_: Path, no: str, hid_id: str, numero_de: str | None = None) -> None:
    """Um hidraw ``no`` no ``/sys``, com o número do ``/dev/<numero_de>`` (padrão: o próprio).

    Os nós são os de caractere que todo sistema tem (``null``, ``zero``, ``full``): a porta abre
    o ``/dev`` de verdade, sem seguir link, e nenhum hidraw de verdade se abre.
    """
    dispositivo = sys_ / "devices/hid" / no
    dispositivo.mkdir(parents=True, exist_ok=True)
    (dispositivo / "uevent").write_text(f"DRIVER=hid-generic\nHID_ID={hid_id}\n")
    (dispositivo / "report_descriptor").write_bytes(_DA_FABRICANTE)
    classe = sys_ / "class/hidraw" / no
    classe.mkdir(parents=True, exist_ok=True)
    real = _DEV / (numero_de or no)
    numero = os.stat(real).st_rdev if real.exists() else 0
    (classe / "dev").write_text(f"{os.major(numero)}:{os.minor(numero)}\n")
    if not (classe / "device").is_symlink():
        (classe / "device").symlink_to(dispositivo)


def _renascer(sys_: Path, de: str, para: str) -> None:
    """O ``RESET;``: o hidraw ``de`` some e o mesmo adaptador volta como ``para``."""
    shutil.rmtree(sys_ / "class/hidraw" / de)
    _no_de_mentira(sys_, para, _E429)


def test_o_declarado_pela_porta_nunca_entra_na_caixa(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    so_porta = _manifesto(["aparelhos"], [_PELA_PORTA])
    assert sup.aparelhos_que_casam(so_porta, _aceitos(so_porta), sys_) == ()
    misto = _manifesto(["aparelhos"], [_PELA_PORTA, {**_ADAPTADOR, "classe": "tty"}])
    assert sup.aparelhos_que_casam(misto, _aceitos(misto), sys_) == ("/dev/ttyACM0",)


def test_a_lovense_sem_pela_porta_segue_com_o_no_montado(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    velha = _manifesto(["aparelhos"], [_ADAPTADOR, {**_ADAPTADOR, "vid": "1915", "pid": "520a"}])
    assert sup.aparelhos_que_casam(velha, _aceitos(velha), sys_) == ("/dev/hidraw3",)


def test_abrir_o_aparelho_so_abre_o_no_declarado_pelo_sys(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    _no_de_mentira(sys_, "null", _E429)
    _no_de_mentira(sys_, "full", _DUALSENSE)
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    fd = sup.abrir_o_aparelho(manifesto, "null", _aceitos(manifesto), sys_, _DEV)
    try:
        assert os.fstat(fd).st_rdev == _NULO
        assert os.get_inheritable(fd) is False
    finally:
        os.close(fd)
    for torto in ("full", "uinput", "uhid", "input/event3", "hidraw/../uinput", "/dev/null",
                  "../null", "..", "", 7, None, "zero"):
        with pytest.raises(ValueError, match=r"aparelho\.abrir"):
            sup.abrir_o_aparelho(manifesto, torto, _aceitos(manifesto), sys_, _DEV)
    with pytest.raises(ValueError, match=r"aparelho\.abrir"):
        sup.abrir_o_aparelho(_manifesto([]), "null", _aceitos(_manifesto([])), sys_, _DEV)


def test_a_porta_nao_abre_o_usb_cru(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    usb = _manifesto(["aparelhos"], [{**_ADAPTADOR, "classe": "usb"}])
    assert sup.aparelhos_que_casam(usb, _aceitos(usb), sys_) == ("/dev/bus/usb/003/007",)
    assert sup.nos_pela_porta(usb, _aceitos(usb), sys_) == {}
    classes = ("hidraw", "tty", "usb")
    tudo = _manifesto(["aparelhos"], [{**_ADAPTADOR, "classe": c} for c in classes])
    pela_porta = sorted(sup.nos_pela_porta(tudo, _aceitos(tudo), sys_))
    assert pela_porta == ["/dev/hidraw3", "/dev/ttyACM0"]
    with pytest.raises(ValueError, match=r"aparelho\.abrir"):
        sup.abrir_o_aparelho(usb, "bus/usb/003/007", _aceitos(usb), sys_, _DEV)
    with pytest.raises(ValueError, match="não é de um aparelho aceito"):
        sup.abrir_o_aparelho(usb, "007", _aceitos(usb), sys_, _DEV / "bus/usb/003")


def test_o_nome_com_barra_nunca_vira_caminho(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    monkeypatch.setattr(sup, "_casam", lambda *a, **k: {"/dev/input/event3": sys_,
                                                       "/dev/../null": sys_})
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    for torto in ("input/event3", "../null"):
        with pytest.raises(ValueError, match="o no é o nome do nó"):
            sup.abrir_o_aparelho(manifesto, torto, _aceitos(manifesto), sys_, _DEV)


def test_o_numero_do_no_tem_de_bater_com_o_sys(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    _no_de_mentira(sys_, "null", _E429, numero_de="zero")
    with pytest.raises(ValueError, match="mudou de aparelho"):
        sup.abrir_o_aparelho(_SO_PORTA, "null", _aceitos(_SO_PORTA), sys_, _DEV)


def test_o_no_que_e_link_nao_se_segue(tmp_path: Path) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    _no_de_mentira(sys_, "null", _E429)
    dev = tmp_path / "dev"
    dev.mkdir()
    (dev / "null").symlink_to("/dev/null")
    with pytest.raises(OSError):
        sup.abrir_o_aparelho(_SO_PORTA, "null", _aceitos(_SO_PORTA), sys_, dev)


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


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


async def _porta_com_o_aparelho(pasta: Path, manifesto: Manifesto, sys_: Path,
                                pid: int, relogio: _Relogio | None = None) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(pasta / "porta.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: None,
                  relogio=relogio or _Relogio())
    await porta.iniciar()
    porta.registrar("ficha", "exemplo", pid, manifesto.permissoes,
                    abrir_o_aparelho=lambda no: sup.abrir_o_aparelho(
                        manifesto, no, _aceitos(manifesto), sys_, _DEV))
    return porta


def test_o_no_que_renasce_se_pede_de_novo_pela_porta(curto: Path) -> None:
    sys_ = _sys_de_mentira(curto)
    _no_de_mentira(sys_, "null", _E429)
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    relogio = _Relogio()

    async def cena() -> None:
        porta = await _porta_com_o_aparelho(curto, manifesto, sys_, os.getpid(), relogio)
        try:
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("null"))
            assert resposta["result"] == {"no": "null"} and len(fds) == 1, resposta
            assert os.fstat(fds[0]).st_rdev == _NULO
            os.close(fds[0])
            _renascer(sys_, "null", "zero")
            relogio.agora += 1
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("null"))
            assert "error" in resposta and fds == [], "o nó que sumiu não abre mais"
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("zero"))
            assert resposta["result"] == {"no": "zero"} and len(fds) == 1, resposta
            assert os.fstat(fds[0]).st_rdev == _ZERO
            assert os.write(fds[0], b"RESET;\r\n") == 8
            os.close(fds[0])
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho,
                                                    _abrir("zero", "outra"))
            assert resposta["error"]["message"] == "ficha desconhecida" and fds == []
        finally:
            await porta.parar()

    asyncio.run(cena())


def test_o_aparelho_abrir_tem_teto_por_segundo(curto: Path) -> None:
    sys_ = _sys_de_mentira(curto)
    _no_de_mentira(sys_, "null", _E429)
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    relogio = _Relogio()

    async def cena() -> None:
        porta = await _porta_com_o_aparelho(curto, manifesto, sys_, os.getpid(), relogio)
        try:
            for _ in range(APARELHOS_POR_SEGUNDO):
                resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho,
                                                        _abrir("null"))
                assert len(fds) == 1, resposta
                os.close(fds[0])
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("null"))
            assert resposta["error"]["code"] == CODE_TETO_CHEIO and fds == [], resposta
            relogio.agora += 1
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("null"))
            assert len(fds) == 1, "passado o segundo, o pedido volta a sair"
            os.close(fds[0])
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
            resposta, fds = await asyncio.to_thread(_pedir_o_fd, porta.caminho, _abrir("null"))
            assert resposta["error"]["code"] == CODE_SEM_PERMISSAO and fds == [], resposta
        finally:
            await porta.parar()

    asyncio.run(cena())


def test_o_aparelho_abrir_so_vale_como_primeira_palavra(curto: Path) -> None:
    sys_ = _sys_de_mentira(curto)
    _no_de_mentira(sys_, "null", _E429)
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])

    def depois_do_ola(caminho: Path) -> tuple[dict[str, Any], list[int]]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(str(caminho))
            ola = {"jsonrpc": "2.0", "id": 0, "method": "mod.ola", "params": {"ficha": "ficha"}}
            sock.sendall((json.dumps(ola) + "\n" + json.dumps(_abrir("null")) + "\n").encode())
            lido, fds = b"", list[int]()
            while lido.count(b"\n") < 2:
                cru, novos, _, _ = socket.recv_fds(sock, 65536, 1)
                lido, fds = lido + cru, fds + novos
        return json.loads(lido.splitlines()[1]), fds

    async def cena() -> None:
        porta = await _porta_com_o_aparelho(curto, manifesto, sys_, os.getpid())
        try:
            resposta, fds = await asyncio.to_thread(depois_do_ola, porta.caminho)
            assert "desconhecido" in resposta["error"]["message"] and fds == [], resposta
        finally:
            await porta.parar()

    asyncio.run(cena())


def test_o_sim_e_a_chave_se_conferem_a_cada_pedido(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys_ = _sys_de_mentira(tmp_path)
    _no_de_mentira(sys_, "null", _E429)
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    real = sup.abrir_o_aparelho
    monkeypatch.setattr(sup, "abrir_o_aparelho",
                        lambda m, no, aceitos: real(m, no, aceitos, sys_, _DEV))
    entrada = SimpleNamespace(ligada=True, permissoes_aceitas=["aparelhos"],
                              aparelhos_aceitos=["hidraw:1a86:e429"])
    monkeypatch.setattr(sup, "ler_registro", lambda caminho: {"exemplo": entrada})
    supervisor = sup.Supervisor.__new__(sup.Supervisor)
    supervisor.lugares = SimpleNamespace(registro=tmp_path / "registro.json")  # type: ignore[assignment]
    supervisor._vigiadas = {"exemplo": sup._Vigiada("exemplo", ficha="ficha")}
    abrir = supervisor._abridor_dos_aparelhos(manifesto, "ficha")
    assert abrir is not None
    os.close(abrir("null"))
    entrada.ligada = False
    with pytest.raises(ValueError, match="não está ligada"):
        abrir("null")
    entrada.ligada, entrada.permissoes_aceitas = True, []
    with pytest.raises(ValueError, match="não tem o «sim»"):
        abrir("null")
    entrada.permissoes_aceitas = ["aparelhos"]
    supervisor._vigiadas = {"exemplo": sup._Vigiada("exemplo", ficha="outra")}
    with pytest.raises(ValueError, match="não está mais de pé"):
        abrir("null")
    assert supervisor._abridor_dos_aparelhos(_manifesto(["aparelhos"]), "ficha") is None


_NA_CAIXA = """
import json, os, socket, sys, time
caminho, no = sys.argv[1], sys.argv[2]
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
    time.sleep(0.25)
print("resposta", json.dumps(resposta))
print("rdev", os.fstat(fds[0]).st_rdev if fds else None)
print("escreveu", os.write(fds[0], b"DeviceType;\\r\\n") if fds else None)
"""


def test_com_o_bwrap_real_o_no_que_renasce_chega_pela_porta(curto: Path) -> None:
    """D-1511-O-APARELHO-QUE-RENASCE-VEM-PELA-PORTA."""
    exigir_caixa_do_bwrap()
    sys_ = _sys_de_mentira(curto)
    _no_de_mentira(sys_, "null", _E429)
    _renascer(sys_, "null", "zero")
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])

    async def cena() -> str:
        porta = await _porta_com_o_aparelho(curto, manifesto, sys_, -1)
        argv = _caixa(curto, manifesto, ["/usr/bin/python3", "-I", "-c", _NA_CAIXA,
                                         str(porta.caminho), "zero"],
                      aparelhos=sup.aparelhos_que_casam(manifesto, _aceitos(manifesto), sys_))
        assert "--dev-bind-try" not in argv and "--dev-bind" not in argv
        processo = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        porta.registrar("ficha", "exemplo", processo.pid, manifesto.permissoes,
                        abrir_o_aparelho=lambda no: sup.abrir_o_aparelho(
                            manifesto, no, _aceitos(manifesto), sys_, _DEV))
        try:
            saida, _ = await asyncio.wait_for(processo.communicate(), timeout=60)
        finally:
            await porta.parar()
        return saida.decode()

    saida = asyncio.run(cena())
    visto = dict(linha.split(" ", 1) for linha in saida.splitlines() if " " in linha)
    assert json.loads(visto["resposta"]).get("result") == {"no": "zero"}, saida
    assert visto["rdev"] == str(_ZERO), saida
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
                           manifesto=manifesto, aparelhos=aparelhos,
                           aceitos=tuple(_aceitos(manifesto)))
    supervisor._vigiadas = {"exemplo": vigiada}

    async def comecar(entrada: Any) -> None:
        reabertas.append("exemplo")
        vigiada.aparelhos = sup.aparelhos_que_casam(manifesto, vigiada.aceitos)
        vigiada.aparelho_novo = False

    supervisor._comecar = comecar  # type: ignore[method-assign]
    return supervisor, vigiada, reabertas


def test_o_reset_do_adaptador_pela_porta_nunca_reabre_a_caixa(
        curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys_ = _sys_de_mentira(curto)
    real = sup.aparelhos_que_casam
    monkeypatch.setattr(sup, "aparelhos_que_casam",
                        lambda m, aceitos, *a: real(m, aceitos, sys_))
    _no_de_mentira(sys_, "hidraw20", _E429)
    manifesto = _manifesto(["aparelhos"], [_PELA_PORTA])
    supervisor, _vigiada, reabertas = _vigia_de_mentira(manifesto, ())

    async def resets() -> None:
        atual = "hidraw20"
        for numero in range(21, 27):
            _renascer(sys_, atual, f"hidraw{numero}")
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
