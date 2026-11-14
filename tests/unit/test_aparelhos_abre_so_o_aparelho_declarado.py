"""A permissão ``aparelhos`` abre só o aparelho declarado.

Sprint APARELHOS-ABRE-SO-O-APARELHO-DECLARADO-01.

O manifesto declara a classe (``hidraw``, ``tty``, ``usb``) e o VID:PID; a caixa fica com o ``/dev``
mínimo do ``bwrap`` e recebe só os nós que casam. O ``uinput``, o ``uhid`` e o ``input/`` nunca
entram, nem o controle e o teclado. O aparelho que entra depois da abertura reabre a caixa.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto
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
