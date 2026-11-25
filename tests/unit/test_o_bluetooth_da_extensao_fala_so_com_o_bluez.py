"""O Bluetooth da extensão fala só com o BlueZ.

O barramento do sistema é o ``dbus-daemon`` particular de ``bluez_de_mentira`` (nenhuma prova fala
com o BlueZ nem com o barramento de verdade); a caixa é o ``bwrap`` de verdade e o filtro é o
``xdg-dbus-proxy`` de verdade, e as provas de dentro da caixa pulam sem eles. As sondas só
fazem chamadas que, no barramento de verdade, dariam objeto desconhecido ou nada.

MORDIDAS (25/11/2026, executadas sobre a cura e devolvidas):

- o ``/run/dbus`` devolvido ao ``DEVOLVIDO_COM_A_PERMISSAO`` reprova
  ``test_a_linha_montada_nao_traz_o_run_dbus``;
- o ``RemoveDevice`` posto no filtro reprova
  ``test_o_filtro_do_bluez_nao_traz_o_que_desliga_ou_esquece`` e
  ``test_de_dentro_da_caixa_so_o_bluez_responde``;
- o proxy tirado do ``_abrir`` reprova ``test_de_dentro_da_caixa_so_o_bluez_responde``;
- a recusa tirada do ``_comecar`` reprova ``test_sem_o_proxy_a_extensao_com_bluetooth_recusa``;
- o ``_soltar_o_proxy`` tirado da falha de abertura do ``_cuidar`` reprova
  ``test_a_abertura_que_falha_depois_do_proxy_o_solta``.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.instalador import Lugares, instalar
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit import bluez_de_mentira as bm
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

curto, lar = _base.curto, _base.lar
_ate, _supervisor, _ligar_vendo = _base._ate, _base._supervisor, _base._ligar_vendo
_manifesto = _base._manifesto

_NA_CAIXA = "/run/dbus/system_bus_socket"

_SONDA = textwrap.dedent('''
    import json, os, time
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    saida = {"endereco": os.environ.get("DBUS_SYSTEM_BUS_ADDRESS", "")}
    c = Gio.DBusConnection.new_for_address_sync(
        saida["endereco"],
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None)

    def chamar(destino, caminho, interface, chamada, parametros=None):
        try:
            c.call_sync(destino, caminho, interface, chamada, parametros, None,
                        Gio.DBusCallFlags.NONE, 5000, None)
            return "ok"
        except GLib.Error as erro:
            return erro.message.rsplit(".", 1)[-1][:40]

    r = c.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                    "ListNames", None, None, Gio.DBusCallFlags.NONE, 5000, None)
    saida["nomes"] = [n for n in r.unpack()[0] if not n.startswith(":")]
    V = GLib.Variant
    saida["objetos"] = chamar("org.bluez", "/", "org.freedesktop.DBus.ObjectManager",
                              "GetManagedObjects")
    saida["procurar"] = chamar("org.bluez", "/org/bluez/hci9", "org.bluez.Adapter1",
                               "StartDiscovery")
    saida["esquecer"] = chamar("org.bluez", "/org/bluez/hci9", "org.bluez.Adapter1",
                               "RemoveDevice", V("(o)", ("/org/bluez/hci9/dev_00_00_00_00_00_00",)))
    saida["desligar"] = chamar("org.bluez", "/org/bluez/hci9", "org.freedesktop.DBus.Properties",
                               "Set", V("(ssv)", ("org.bluez.Adapter1", "Powered", V("b", False))))
    saida["logind"] = chamar("org.freedesktop.login1", "/org/freedesktop/login1",
                             "org.freedesktop.DBus.Peer", "Ping")
    with open(os.path.join(os.environ["HEFESTO_MOD_DADOS"], "relato.json"), "w") as f:
        json.dump(saida, f)
    while True:
        time.sleep(1)
''')


def _manifesto_do_bluetooth() -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": ["bluetooth"],  # (noqa-acento)
    })


def _caixa(base: Path, **mais: str | None) -> list[str]:
    for pasta in ("fonte", "dados", "casa"):
        (base / pasta).mkdir(exist_ok=True)
    porta = base / "porta.sock"
    porta.touch()
    return sup.comando_na_caixa(
        bwrap=shutil.which("bwrap") or "bwrap", comando=["true"], codigo=base / "fonte",
        dados=base / "dados", porta=porta, manifesto=_manifesto_do_bluetooth(),
        casa=base / "casa", execucao=(), **mais)


def test_a_linha_montada_nao_traz_o_run_dbus(curto: Path) -> None:
    """D-2511-O-BLUETOOTH-DA-EXTENSAO-FALA-SO-COM-O-BLUEZ: só o soquete do proxy entra."""
    assert "/run/dbus" not in sup.DEVOLVIDO_COM_A_PERMISSAO["bluetooth"]
    sem_proxy = _caixa(curto)
    assert "/run/dbus" not in sem_proxy and _NA_CAIXA not in sem_proxy
    soquete = str(curto / "bluez.sock")
    com_proxy = _caixa(curto, bluez=soquete)
    assert "/run/dbus" not in com_proxy
    i = com_proxy.index(_NA_CAIXA)
    assert com_proxy[i - 2:i + 1] == ["--bind", soquete, _NA_CAIXA]


def test_o_filtro_do_bluez_nao_traz_o_que_desliga_ou_esquece() -> None:
    """D-2511-O-BLUETOOTH-DA-EXTENSAO-FALA-SO-COM-O-BLUEZ: procurar fica; esquecer e ligar, não."""
    filtro = " ".join(sup.FILTRO_DO_BLUEZ)
    assert "--filter" in sup.FILTRO_DO_BLUEZ and "--talk" not in filtro
    for fica in ("Adapter1.StartDiscovery", "Adapter1.StopDiscovery", "Device1.Connect",
                 "Device1.Disconnect", "ObjectManager.GetManagedObjects",
                 "GattCharacteristic1.WriteValue"):
        assert fica in filtro, fica
    for fora in ("RemoveDevice", "Properties.Set", "Device1.Pair", "login1", "NetworkManager"):
        assert fora not in filtro, fora


def _tem_o_proxy() -> bool:
    return shutil.which("xdg-dbus-proxy") is not None and bm.ha_dbus_daemon()


@pytest.mark.skipif(not _tem_o_proxy(), reason="sem xdg-dbus-proxy, dbus-daemon ou Gio")
def test_de_dentro_da_caixa_so_o_bluez_responde(
        curto: Path, lar: Lugares, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2511-O-BLUETOOTH-DA-EXTENSAO-FALA-SO-COM-O-BLUEZ: vê o org.bluez, nada além dele."""
    exigir_caixa_do_bwrap()
    pasta = curto / "fonte-exemplo"
    pasta.mkdir()
    corpo = _manifesto(permissoes=["bluetooth"])  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")
    (pasta / "mod.py").write_text(_SONDA, encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    (curto / "bus").mkdir()
    with bm.BluezParticular(curto / "bus") as bluez:
        monkeypatch.setenv("DBUS_SYSTEM_BUS_ADDRESS", bluez.endereco)
        sistema = bluez.outro_cliente()
        sistema.chamar("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                       "RequestName", sistema.GLib.Variant("(su)", ("org.freedesktop.login1", 0)))
        sup_ = _supervisor(lar)
        visto: dict[str, object] = {}
        proxies: list[int] = []

        async def corrida() -> None:
            await sup_.iniciar()
            try:
                await _ate(lambda: (lar.dados / "exemplo" / "relato.json").exists(), prazo=20.0)
                visto.update(json.loads((lar.dados / "exemplo" / "relato.json").read_text()))
                vigiada = sup_._vigiadas["exemplo"]
                assert vigiada.proxy is not None
                proxies.append(vigiada.proxy.pid)
            finally:
                await sup_.parar()

        asyncio.run(corrida())
        metodos = [c[3] for c in bluez.chamadas]
    assert visto["endereco"] == f"unix:path={_NA_CAIXA}"
    assert "org.bluez" in visto["nomes"] and "org.freedesktop.login1" not in visto["nomes"]  # type: ignore[operator]
    assert (visto["objetos"], visto["procurar"]) == ("ok", "ok")
    assert visto["esquecer"] == "AccessDenied" and visto["desligar"] == "AccessDenied"
    assert visto["logind"] in ("AccessDenied", "ServiceUnknown"), visto
    assert "RemoveDevice" not in metodos and "Set" not in metodos, metodos
    assert "StartDiscovery" in metodos
    with pytest.raises(ProcessLookupError):
        os.kill(proxies[0], 0)


_PROXY_DE_MENTIRA = textwrap.dedent('''\
    #!{python}
    import os, sys, time
    fd = int(next(a for a in sys.argv if a.startswith("--fd="))[5:])
    open({pid!r}, "w").write(str(os.getpid()))
    os.write(fd, b"x")
    time.sleep(600)
''')


def test_a_abertura_que_falha_depois_do_proxy_o_solta(curto: Path, lar: Lugares) -> None:
    """D-2511-O-BLUETOOTH-DA-EXTENSAO-FALA-SO-COM-O-BLUEZ: a caixa que não abre leva o proxy."""
    pasta = curto / "fonte-exemplo"
    pasta.mkdir()
    corpo = _manifesto(permissoes=["bluetooth"])  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")
    (pasta / "mod.py").write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    marca = curto / "pid-do-proxy"
    proxy = curto / "proxy-de-mentira"
    proxy.write_text(_PROXY_DE_MENTIRA.format(python=sys.executable, pid=str(marca)),
                     encoding="utf-8")
    proxy.chmod(0o700)
    sup_ = _supervisor(lar, bwrap=shutil.which("bwrap") or "/usr/bin/bwrap",
                       proxy_dbus=str(proxy), systemd_run=str(curto / "sem-systemd-run"))

    async def corrida() -> None:
        await sup_.iniciar()
        try:
            await _ate(lambda: (e := sup_.estado_de("exemplo")) is not None
                       and e.estado == "parou")
            assert marca.exists(), "o proxy nem abriu: a falha veio antes dele"
            assert sup_._vigiadas["exemplo"].proxy is None, "o proxy ficou aberto"
            with pytest.raises(ProcessLookupError):
                os.kill(int(marca.read_text()), 0)
        finally:
            await sup_.parar()

    asyncio.run(corrida())


def test_sem_o_proxy_a_extensao_com_bluetooth_recusa(curto: Path, lar: Lugares) -> None:
    """D-2511-O-BLUETOOTH-DA-EXTENSAO-FALA-SO-COM-O-BLUEZ: sem o filtro, não abre, com frase."""
    pasta = curto / "fonte-exemplo"
    pasta.mkdir()
    corpo = _manifesto(permissoes=["bluetooth"])  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")
    (pasta / "mod.py").write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    sup_ = _supervisor(lar, bwrap="/usr/bin/bwrap", procurar_proxy_dbus=False)

    async def corrida() -> None:
        await sup_.reconciliar()
        estado = sup_.estado_de("exemplo")
        assert estado is not None and estado.estado == "recusada"
        assert estado.motivo == sup.FALTA_O_PROXY_DO_BLUETOOTH
        assert not sup_._vigiadas

    asyncio.run(corrida())
