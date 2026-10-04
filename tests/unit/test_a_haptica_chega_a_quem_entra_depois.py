"""A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01 — o cabo passa pelo endpoint, e o registro tem dono."""

from __future__ import annotations

import itertools
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.haptica_do_cabo import (
    MAPA,
    HapticaDoCabo,
    chave_do_aparelho,
    no_de_captura,
)
from tests.unit.test_haptica_nativa_01_o_device_ks_que_o_jogo_procura import (
    _DaemonQueResponde,
    _path_minimo,
)

RAIZ = Path(__file__).resolve().parents[2]
WRAPPER = RAIZ / "assets" / "hefesto-launch.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

_P1, _P2, _P3, _P4 = (f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))

#: O que o GE lê de um DualSense de verdade no proplist, e o que o nosso nó veste.
_SONY = {"device.bus": "usb", "device.vendor.id": "054c", "device.product.id": "0ce6"}


# O /sys de mentira: âncoras (USB sem placa de som) e DualSense no cabo


def _aparelho(
    sysfs: Path, nome: str, *, vid: str, pid: str, devnum: int, placa: bool = False
) -> Path:
    """Um ``usb_device`` em ``devices/``, com o atalho em ``bus/usb/devices``.

    O atalho é o que o kernel publica, e é por ele que ``ancoras()`` e
    ``controles_no_cabo()`` leem; o caminho resolvido é o que o nó declara.
    """
    real = sysfs / "devices" / "pci0000:00" / "usb3" / nome
    interface = real / f"{nome}:1.0"
    interface.mkdir(parents=True)
    (interface / "uevent").write_text("DEVTYPE=usb_interface\n", encoding="utf-8")
    if placa:
        (interface / "sound" / "card2").mkdir(parents=True)
    for arquivo, valor in (
        ("idVendor", vid), ("idProduct", pid), ("busnum", "3"), ("devnum", str(devnum)),
    ):
        (real / arquivo).write_text(f"{valor}\n", encoding="utf-8")
    atalhos = sysfs / "bus" / "usb" / "devices"
    atalhos.mkdir(parents=True, exist_ok=True)
    (atalhos / nome).symlink_to(real)
    return real


def _sysfs(tmp_path: Path, *, ancoras: int, no_cabo: int = 0) -> Path:
    sysfs = tmp_path / "sys"
    for i in range(ancoras):
        _aparelho(sysfs, f"3-{i + 1}", vid="2357", pid="0604", devnum=10 + i)
    for i in range(no_cabo):
        _aparelho(sysfs, f"3-{8 - i}", vid="054c", pid="0ce6", devnum=28 + i, placa=True)
    return sysfs


def _caminho_da_placa(nome_do_aparelho: str) -> str:
    return f"/devices/pci0000:00/usb3/{nome_do_aparelho}/{nome_do_aparelho}:1.0/sound/card2"


#: O nome da placa de um DualSense no cabo, como o ALSA a publica; dois no cabo
_PLACA = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller"
    "-00{n}.HiFi__Speaker__sink"
)


def _props_do_argumento(argumento: str) -> dict[str, str]:
    """O ``sink_properties="…"`` como o ``pipewire-pulse`` o lê (aspas de fora)."""
    valor = argumento.split("=", 1)[1]
    miolo = valor[1:-1] if valor.startswith('"') and valor.endswith('"') else valor.split(" ", 1)[0]
    campos: dict[str, str] = {}
    for pedaco in shlex.split(miolo):
        chave, igual, resto = pedaco.partition("=")
        if igual:
            campos[chave] = resto
    return campos


class _Servidor:
    """Um ``pipewire-pulse`` de mentira: módulos, sinks, fluxos e volumes."""

    def __init__(self) -> None:
        self.sinks: dict[int, dict[str, Any]] = {}
        self.modulos: dict[str, str] = {}
        self.fluxos: dict[int, dict[str, Any]] = {}
        self.volumes: dict[int, list[str]] = {}
        self.jogo_em: set[str] = set()
        self.cargas: list[str] = []
        self.quedas: list[str] = []
        self._n = 100

    def _proximo(self) -> int:
        self._n += 1
        return self._n


    def placa(self, nome: str, caminho: str) -> int:
        """A placa de som de um DualSense no cabo, como o ALSA a publica."""
        indice = self._proximo()
        self.sinks[indice] = {
            "nome": nome, "props": {**_SONY, "sysfs.path": caminho}, "canais": 4, "mid": None,
        }
        return indice

    def modulo_herdado(self, nome: str, caminho: str) -> str:
        """Um endpoint que um processo ANTERIOR do daemon deixou de pé."""
        props = " ".join(f"{k}={v}" for k, v in {**_SONY, "sysfs.path": caminho}.items())
        resposta = self(["pactl", "load-module", "module-null-sink", f"sink_name={nome}",
                         "channels=4", f'sink_properties="{props}"'])
        assert resposta
        self.cargas.clear()
        return resposta.strip()


    def laco_toca(self, chave: str, destino: str) -> None:
        self.fluxos[self._proximo()] = {
            "sink": int(destino), "nome": f"output.hefesto-haptica-do-cabo-{chave}",
        }

    def laco_sai(self, chave: str) -> None:
        self.fluxos = {
            i: f for i, f in self.fluxos.items()
            if f["nome"] != f"output.hefesto-haptica-do-cabo-{chave}"
        }

    def fluxo_do_laco(self, uniq: str) -> int:
        (indice,) = [
            i for i, f in self.fluxos.items()
            if f["nome"] == f"output.hefesto-haptica-do-cabo-{_chave(uniq)}"
        ]
        return indice


    def do_nome(self, nome: str) -> list[dict[str, Any]]:
        return [s for s in self.sinks.values() if s["nome"] == nome]

    def indice(self, nome: str) -> int:
        (achado,) = [i for i, s in self.sinks.items() if s["nome"] == nome]
        return achado

    def nossos(self) -> list[str]:
        return sorted(s["nome"] for s in self.sinks.values() if eh.MARCA_DO_NOME in s["nome"])


    def __call__(self, argv: list[str]) -> str | None:
        a = list(argv)
        if a[:2] == ["pactl", "info"]:
            return "Server Name: PulseAudio (on PipeWire 1.2.7)\n"
        if a[:2] == ["pactl", "load-module"]:
            nome = next((x.split("=", 1)[1] for x in a if x.startswith("sink_name=")), "")
            if not nome or len(nome) > eh.MAX_NOME:
                return None
            canais = int(next((x.split("=", 1)[1] for x in a if x.startswith("channels=")), "2"))
            props = next(
                (_props_do_argumento(x) for x in a if x.startswith("sink_properties=")), {}
            )
            mid = str(self._proximo())
            self.modulos[mid] = " ".join(a[3:])
            self.sinks[self._proximo()] = {
                "nome": nome, "props": props, "canais": canais, "mid": mid,
            }
            self.cargas.append(nome)
            return f"{mid}\n"
        if a[:2] == ["pactl", "unload-module"]:
            mid = a[2]
            if mid not in self.modulos:
                return None
            del self.modulos[mid]
            saem = {i for i, s in self.sinks.items() if s["mid"] == mid}
            self.sinks = {i: s for i, s in self.sinks.items() if i not in saem}
            self.fluxos = {i: f for i, f in self.fluxos.items() if f["sink"] not in saem}
            self.quedas.append(mid)
            return ""
        if a[:4] == ["pactl", "list", "short", "modules"]:
            return "\n".join(f"{m}\tmodule-null-sink\t{arg}\t" for m, arg in self.modulos.items())
        if a[:4] in (["pactl", "list", "short", "sinks"], ["pactl", "list", "sinks", "short"]):
            return "\n".join(
                f"{i}\t{s['nome']}\tPipeWire\tfloat32le {s['canais']}ch 48000Hz\tIDLE"
                for i, s in self.sinks.items()
            )
        if a[:3] == ["pactl", "list", "sinks"]:
            blocos = []
            for i, s in self.sinks.items():
                props = "\n".join(f'\t\t{k} = "{v}"' for k, v in s["props"].items())
                blocos.append(
                    f"Sink #{i}\n\tState: IDLE\n\tName: {s['nome']}\n"
                    f"\tSample Specification: float32le {s['canais']}ch 48000Hz\n"
                    f"\tProperties:\n{props}"
                )
            return "\n\n".join(blocos)
        if a[:4] in (
            ["pactl", "list", "short", "sink-inputs"], ["pactl", "list", "sink-inputs", "short"]
        ):
            linhas = [
                f"9{i}\t{i}\t42\tprotocol-native.c\tfloat32le 4ch 48000Hz"
                for i, s in self.sinks.items() if s["nome"] in self.jogo_em
            ]
            linhas += [
                f"{i}\t{f['sink']}\t77\tPipeWire\tfloat32le 4ch 48000Hz"
                for i, f in self.fluxos.items()
            ]
            return "\n".join(linhas)
        if a[:3] == ["pactl", "list", "sink-inputs"]:
            return "\n\n".join(
                f"Sink Input #{i}\n\tDriver: PipeWire\n\tSink: {f['sink']}\n"
                f"\tProperties:\n\t\tnode.name = \"{f['nome']}\""
                for i, f in self.fluxos.items()
            )
        if a[:4] == ["pactl", "list", "short", "clients"]:
            return "42\tprotocol-native.c\tjogo\n77\tPipeWire\tpw-loopback\n"
        if a[:2] == ["pactl", "set-sink-input-volume"]:
            indice = int(a[2])
            if indice not in self.fluxos:
                return None
            self.volumes[indice] = a[3:]
            return ""
        return ""


class _Lacos:
    """O dono dos laços de mentira: o laço que sobe vira um fluxo na placa."""

    def __init__(self, servidor: _Servidor) -> None:
        self.servidor = servidor
        self.vivos: dict[str, dict[str, Any]] = {}
        self.ligacoes: list[tuple[str, str, str, int, str]] = []

    def esta_ligado(self, chave: str) -> bool:
        return chave in self.vivos

    def ligar(self, chave: str, *, captura: str, destino: str = "", canais: int = 1,
              mapa: str = "[ MONO ]") -> bool:
        if chave in self.vivos:
            return True
        self.vivos[chave] = {"captura": captura, "destino": destino}
        self.ligacoes.append((chave, captura, destino, canais, mapa))
        self.servidor.laco_toca(chave, destino)
        return True

    def desligar(self, chave: str) -> bool:
        if self.vivos.pop(chave, None) is None:
            return False
        self.servidor.laco_sai(chave)
        return True


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.kw = kw
        self.motivo = ""
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu

    @property
    def leva(self) -> bool:
        """O bloco da háptica vai ao fio agora (o ``leva_a_haptica`` que a ponte lê)."""
        leva = self.kw.get("leva_a_haptica", False)
        return bool(leva() if callable(leva) else leva)


@dataclass
class _Controle:
    uniq: str
    transporte: str
    caminho: str = "/dev/hidraw9"


@dataclass
class _Mesa:
    sub: Any
    servidor: _Servidor
    lacos: _Lacos
    sysfs: Path
    assentos: dict[str, int] = field(default_factory=dict)
    placas: dict[str, str] = field(default_factory=dict)
    jogando: set[str] = field(default_factory=set)
    lidos: list[tuple[str, str]] = field(default_factory=list)

    def volta(self, *controles: _Controle) -> None:
        self.sub._casar_as_pontes(list(controles))

    def registro(self) -> list[ks.Controle]:
        """A lista que o curador gravaria AGORA, perguntando a este servidor."""
        return ks.controles_do_registro(self.sysfs, self.sysfs / "udev", self.servidor)


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Mesa:
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    servidor = _Servidor()
    lacos = _Lacos(servidor)
    sysfs = _sysfs(tmp_path, ancoras=4)
    sub = mod.AltoFalanteSubsystem(gerenciador=None, fonte_de_controles=list)
    sub._cabo = HapticaDoCabo(lacos=lacos, conferir=lambda _no: None)
    m = _Mesa(sub=sub, servidor=servidor, lacos=lacos, sysfs=sysfs)
    monkeypatch.setattr(af, "_rodar", servidor)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", sysfs)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "garantir_motores_audiveis", lambda *_a, **_k: False)
    monkeypatch.setattr(af, "sink_do_controle", lambda uniq, *_a, **_k: m.placas.get(uniq, ""))

    def _fonte(no: str, **kw: Any) -> tuple[Any, Any, str]:
        m.lidos.append((no, str(kw.get("papel", ""))))
        return (lambda _n: b""), f"gravador:{no}", ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, c: set())
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_mexeu_na_partida",
        lambda self, c: {u.lower() for u in m.jogando},
    )
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "numero_do_assento", lambda self, u: m.assentos.get(u)
    )
    return m


def _chave(uniq: str) -> str:
    """A chave do laço do cabo deste controle: a marca do aparelho."""
    return chave_do_aparelho(eh.marca_do_aparelho(uniq))


def _ancora_do_aparelho(servidor: _Servidor, uniq: str) -> str:
    (no,) = servidor.do_nome(eh.nome_do_endpoint(uniq))
    return str(no["props"]["sysfs.path"])


def _instancias(controles: list[ks.Controle]) -> set[str]:
    """As instâncias ``HEFESTOKS&<bus>&<dev>&<n>`` que o registro ganharia."""
    texto = ks.texto_novo("WINE REGISTRY Version 2\n", controles, 1)
    return set(re.findall(r"HEFESTOKS&\d{3}&\d{3}&\d", texto))


def _do_aparelho(sysfs: Path, nome: str) -> str:
    devnum = int((sysfs / "bus" / "usb" / "devices" / nome / "devnum").read_text())
    return f"HEFESTOKS&003&{devnum:03d}&0"


def _no_cabo(mesa: _Mesa, uniq: str, lugar: int, aparelho: str, devnum: int) -> _Controle:
    """Um DualSense no cabo: o aparelho no ``/sys``, a placa no servidor e o número."""
    if not (mesa.sysfs / "bus" / "usb" / "devices" / aparelho).exists():
        _aparelho(mesa.sysfs, aparelho, vid="054c", pid="0ce6", devnum=devnum, placa=True)
    placa = _PLACA.format(n="" if lugar == 1 else f".{lugar}")
    mesa.servidor.placa(placa, _caminho_da_placa(aparelho))
    mesa.placas[uniq] = placa
    mesa.assentos[uniq] = lugar
    return _Controle(uniq, "usb")


_LUGAR = {_P1: 1, _P2: 2, _P3: 3, _P4: 4}
_NO_CABO = {_P1: ("3-8", 28), _P2: ("3-7", 29)}
_ORDENS = list(itertools.permutations((_P1, _P2, _P3, _P4)))


@pytest.mark.parametrize(
    "ordem", _ORDENS, ids=["".join(u[-1] for u in o) for o in _ORDENS]
)
def test_em_qualquer_ordem_cada_um_que_chega_ganha_o_endpoint_dele(
    mesa: _Mesa, ordem: tuple[str, ...]
) -> None:
    """O critério «por controle», nas 24 ordens, pelo aparelho."""
    chegaram: list[_Controle] = []
    for uniq in ordem:
        if uniq in _NO_CABO:
            aparelho, devnum = _NO_CABO[uniq]
            chegaram.append(_no_cabo(mesa, uniq, _LUGAR[uniq], aparelho, devnum))
        else:
            mesa.assentos[uniq] = _LUGAR[uniq]
            chegaram.append(_Controle(uniq, "bt", f"/dev/hidraw{_LUGAR[uniq]}"))
        cargas = list(mesa.servidor.cargas)
        mesa.volta(*chegaram)
        assert mesa.servidor.nossos() == sorted(eh.nome_do_endpoint(c.uniq) for c in chegaram)
        assert mesa.servidor.cargas[len(cargas):] == [eh.nome_do_endpoint(uniq)], (
            f"a chegada de {uniq} não fez nascer só o nó dele"
        )
        assert len(_instancias(mesa.registro())) == len(chegaram)
    assert mesa.servidor.quedas == []
    assert set(mesa.lacos.vivos) == {_chave(_P1), _chave(_P2)}


def test_o_replug_nao_muda_o_endpoint_e_o_laco_segue_a_placa_nova(mesa: _Mesa) -> None:
    """O P1 volta com ``DEVNUM`` novo: o endpoint e o bloco do aparelho ficam.

    MORDIDA: em ``controles_do_registro``, devolva ``controles_no_cabo(...) +
    endpoints`` sem tirar as placas servidas — o bloco volta a ser pelo
    ``BUSNUM-DEVNUM``, e o replug o troca.
    """
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    antes = mesa.registro()
    ancora = _ancora_do_aparelho(mesa.servidor, _P1)
    (primeira,) = [lig for lig in mesa.lacos.ligacoes if lig[0] == _chave(_P1)]
    velha = mesa.placas[_P1]
    mesa.servidor.sinks = {i: s for i, s in mesa.servidor.sinks.items() if s["nome"] != velha}
    (mesa.sysfs / "bus" / "usb" / "devices" / "3-8" / "devnum").write_text("41\n")
    nova = _PLACA.format(n=".9")
    mesa.servidor.placa(nova, _caminho_da_placa("3-8"))
    mesa.placas[_P1] = nova
    mesa.volta(p1)
    assert _ancora_do_aparelho(mesa.servidor, _P1) == ancora
    assert mesa.servidor.quedas == [], "o endpoint do aparelho caiu com o replug"
    ultima = [lig for lig in mesa.lacos.ligacoes if lig[0] == _chave(_P1)][-1]
    assert ultima[2] == str(mesa.servidor.indice(nova)) != primeira[2], "o laço não seguiu a placa"
    depois = mesa.registro()
    assert _instancias(depois) == _instancias(antes), "o bloco do aparelho mudou com o replug"
    assert "HEFESTOKS&003&041&0" not in _instancias(depois)


def test_o_cabo_com_endpoint_ancorado_nao_tem_bloco_proprio(mesa: _Mesa) -> None:
    """A placa e o endpoint seriam dois alvos para o mesmo controle.

    MORDIDA: em ``controles_do_registro``, mantenha o ``controles_no_cabo`` na
    lista (``servidas = set()``).
    """
    mesa.volta(_no_cabo(mesa, _P1, 1, "3-8", 28))
    instancias = _instancias(mesa.registro())
    assert _do_aparelho(mesa.sysfs, "3-8") not in instancias, (
        "o P1 tem bloco pela placa E pelo endpoint"
    )
    assert len(instancias) == 1


def test_so_quem_mexeu_vibra_no_cabo_e_o_alto_falante_passa_nos_dois(mesa: _Mesa) -> None:
    """Dois no cabo, o mesmo sinal nos dois endpoints, e só o P2 mexeu."""
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    p2 = _no_cabo(mesa, _P2, 2, "3-7", 29)
    mesa.servidor.jogo_em.update({eh.nome_do_endpoint(_P1), eh.nome_do_endpoint(_P2)})
    mesa.jogando.add(_P2)
    mesa.volta(p1, p2)
    um = mesa.servidor.volumes[mesa.servidor.fluxo_do_laco(_P1)]
    dois = mesa.servidor.volumes[mesa.servidor.fluxo_do_laco(_P2)]
    assert um == ["100%", "100%", "0%", "0%"], f"o P1 parado vibrou: {um}"
    assert dois == ["100%", "100%", "100%", "100%"], f"o P2 na mão não vibrou: {dois}"
    for _chave_do_laco, captura, destino, canais, mapa in mesa.lacos.ligacoes:
        assert (canais, mapa) == (4, MAPA), "o laço não leva os quatro canais um a um"
        assert captura.isdigit() and destino.isdigit(), "o laço pelo nome cai na fonte padrão"
    assert {lig[1] for lig in mesa.lacos.ligacoes} == {
        str(mesa.servidor.indice(eh.nome_do_endpoint(u))) for u in (_P1, _P2)
    }


def _lancar(tmp_path: Path, sysfs: Path) -> str:
    """Roda o wrapper com a opção ligada pelo daemon; devolve o que o jogo viu."""
    home = tmp_path / "home"
    (home / ".local" / "share" / "hefesto-dualsense4unix" / "bin").mkdir(parents=True)
    estado = tmp_path / "estado"
    pasta = estado / "hefesto-dualsense4unix" / "launch_env"
    pasta.mkdir(parents=True)
    (pasta / "default.env").write_text(
        "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE=1\nPROTON_ENABLE_MHWILDS_USB_AUDIO=1\n",
        encoding="utf-8",
    )
    compat = tmp_path / "compat"
    (compat / "pfx").mkdir(parents=True)
    (compat / "pfx" / "system.reg").write_text("WINE REGISTRY Version 2\n", encoding="utf-8")
    binarios = Path(_path_minimo(tmp_path / "bin"))
    linhas = "\\n".join(
        f"{n}\\t{eh.nome_do_endpoint(u)}\\tPipeWire\\tfloat32le 4ch 48000Hz\\tIDLE"
        for n, u in enumerate((_P1, _P2, _P3, _P4), 1)
    )
    (binarios / "pactl").write_text(f"#!/bin/sh\nprintf '{linhas}\\n'\n", encoding="utf-8")
    (binarios / "pactl").chmod(0o755)
    runtime = Path(tempfile.mkdtemp(prefix="hefks-"))
    (runtime / "hefesto-dualsense4unix").mkdir()
    daemon = _DaemonQueResponde(runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock")
    try:
        feito = subprocess.run(
            ["sh", str(WRAPPER), "sh", "-c",
             'printf "%s\\n" "${PROTON_ENABLE_MHWILDS_USB_AUDIO:-ausente}"'],
            env={
                "PATH": str(binarios), "HOME": str(home), "XDG_RUNTIME_DIR": str(runtime),
                "XDG_STATE_HOME": str(estado), "SteamAppId": "3357650",
                "STEAM_COMPAT_DATA_PATH": str(compat), "HEFESTO_SYSFS": str(sysfs),
            },
            capture_output=True, text=True, timeout=30.0, check=False,
        )
    finally:
        daemon.parar()
        shutil.rmtree(runtime, ignore_errors=True)
    assert feito.returncode == 0, feito.stderr
    return feito.stdout.strip()


def test_os_endpoints_de_pe_sem_dualsense_na_mesa_deixam_a_opcao_em_zero(tmp_path: Path) -> None:
    """Quatro endpoints de pé e nenhum DualSense físico: o Black Desert fica salvo.

    MORDIDA: faça ``dualsense_fisico_na_mesa`` perguntar pelo endpoint
    (``dualsense_no_cabo || pactl list short sinks | grep -q HEFESTO``) — os
    endpoints respondem «há», e a opção liga sem controle nenhum.
    """
    vazio = tmp_path / "sys"
    (vazio / "bus" / "usb" / "devices").mkdir(parents=True)
    (vazio / "bus" / "hid" / "devices").mkdir(parents=True)
    assert _lancar(tmp_path, vazio) == "0"


def test_o_dualsense_no_radio_liga_a_opcao(tmp_path: Path) -> None:
    """Um HID Sony no barramento do Bluetooth é DualSense na mesa; o vpad (USB) não é."""
    sysfs = tmp_path / "sys"
    (sysfs / "bus" / "usb" / "devices").mkdir(parents=True)
    hid = sysfs / "bus" / "hid" / "devices"
    hid.mkdir(parents=True)
    (hid / "0003:054C:0DF2.0009").mkdir()
    assert _lancar(tmp_path / "so-o-vpad", sysfs) == "0"
    (hid / "0005:054C:0CE6.0004").mkdir()
    assert _lancar(tmp_path / "com-o-radio", sysfs) == "1"


def test_o_aparelho_sem_ancora_deixa_o_cabo_na_placa(
    monkeypatch: pytest.MonkeyPatch, mesa: _Mesa, tmp_path: Path
) -> None:
    """Uma âncora e dois no cabo: um pelo endpoint, o outro pelo ``BUSNUM-DEVNUM``."""
    uma = _sysfs(tmp_path / "uma", ancoras=1)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", uma)
    mesa.sysfs = uma
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    p2 = _no_cabo(mesa, _P2, 2, "3-7", 29)
    mesa.volta(p1, p2)
    com, sem = sorted((_P1, _P2), key=eh.marca_do_aparelho)
    aparelho = {_P1: "3-8", _P2: "3-7"}
    assert mesa.servidor.nossos() == [eh.nome_do_endpoint(com)]
    assert set(mesa.lacos.vivos) == {_chave(com)}, "o aparelho sem âncora ganhou laço"
    instancias = _instancias(mesa.registro())
    assert _do_aparelho(uma, aparelho[sem]) in instancias, "o controle sem âncora ficou sem bloco"
    assert _do_aparelho(uma, aparelho[com]) not in instancias, "um controle tem dois alvos"
    assert len(instancias) == 2


def _doctor(tmp_path: Path, sysfs: Path) -> str:
    feito = subprocess.run(
        ["bash", "-c",
         f'source "{DOCTOR}"; '
         f"_python_do_produto() {{ printf '%s\\n' '{sys.executable}'; }}; "
         "check_ancoras_dos_lugares_da_haptica"],
        capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HEFESTO_SYSFS": str(sysfs)},
    )
    return feito.stdout + feito.stderr


def test_o_doctor_diz_o_lugar_sem_ancora(tmp_path: Path) -> None:
    """Dois na mesa e uma âncora: «1 lugar(es) sem âncora»."""
    saida = _doctor(tmp_path, _sysfs(tmp_path, ancoras=1, no_cabo=2))
    assert "[WARN] 1 lugar(es) sem âncora" in saida, saida
    assert "há 1 para 2 DualSense na mesa" in saida


def test_o_doctor_conta_contra_os_quatro_lugares(tmp_path: Path) -> None:
    """Âncoras que bastam para quem está na mesa, e não para os quatro: informação."""
    saida = _doctor(tmp_path, _sysfs(tmp_path, ancoras=2, no_cabo=1))
    assert "[WARN]" not in saida and "[ OK ]" not in saida, saida
    assert "2 âncora(s) USB para os 4 lugares" in saida
    cheio = tmp_path / "cheio"
    cheio.mkdir()
    saida = _doctor(cheio, _sysfs(cheio, ancoras=4, no_cabo=1))
    assert "[ OK ] âncoras USB da vibração: 4 para os 4 lugares" in saida, saida


def test_os_endpoints_de_nome_velho_caem_na_primeira_volta(mesa: _Mesa) -> None:
    """O servidor com os endpoints por controle (até 28/09) e por lugar (28/09 a 02/10)."""
    velhos = [
        mesa.servidor.modulo_herdado(eh.MOLDE_DO_NOME.format(marca=marca), f"/d/{n}/i:1.0")
        for n, marca in enumerate(("0000c3", "0000c4", "LUGAR1", "LUGAR2"))
    ]
    mesa.volta(_Controle(_P3, "bt"))
    assert set(velhos) <= set(mesa.servidor.quedas), "um endpoint de nome velho ficou de pé"
    assert mesa.servidor.nossos() == [eh.nome_do_endpoint(_P3)]


def test_o_endpoint_do_ensaio_nao_e_orfao(mesa: _Mesa) -> None:
    """O nó que a bancada montou pelo ensaio não é resto de processo nenhum."""
    props = " ".join(f"{k}={v}" for k, v in _SONY.items())
    mesa.servidor(["pactl", "load-module", "module-null-sink",
                   f"sink_name={eh.MOLDE_DO_NOME.format(marca='0000c9')}", "channels=4",
                   f'sink_properties="{props} sysfs.path=/d/9/i:1.0 {eh.MARCA_DO_ENSAIO}"'])
    mesa.volta(_Controle(_P3, "bt"))
    assert mesa.servidor.quedas == []


def test_o_laco_cai_antes_do_endpoint_do_aparelho(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O laço cujo alvo some pode ser religado à fonte padrão: ele sai primeiro."""
    mesa.volta(_no_cabo(mesa, _P1, 1, "3-8", 28))
    assert _chave(_P1) in mesa.lacos.vivos
    ordem: list[str] = []
    desligar = mesa.lacos.desligar
    servidor = mesa.servidor

    def _desligar(chave: str) -> bool:
        caiu = desligar(chave)
        if caiu:
            ordem.append(f"laço:{chave}")
        return caiu

    def _pactl(argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "unload-module"]:
            ordem.append("endpoint")
        return servidor(argv)

    monkeypatch.setattr(mesa.lacos, "desligar", _desligar)
    monkeypatch.setattr(af, "_rodar", _pactl)
    mesa.volta()
    assert ordem[:1] == [f"laço:{_chave(_P1)}"], ordem
    assert "endpoint" in ordem


def test_sem_cabo_o_dono_da_lista_nao_pergunta_pelos_fluxos(tmp_path: Path) -> None:
    """Quem joga pelo rádio paga UMA ida ao servidor no lançamento, e não duas."""
    perguntas: list[tuple[str, ...]] = []

    def servidor(argv: list[str]) -> str | None:
        perguntas.append(tuple(argv))
        return ""

    sysfs = _sysfs(tmp_path, ancoras=1)
    assert ks.controles_do_registro(sysfs, tmp_path / "udev", servidor) == []
    assert perguntas == [("pactl", "list", "sinks")]


def test_o_servidor_mudo_cala_a_segunda_pergunta(tmp_path: Path) -> None:
    """O `pactl` que não responde é perguntado UMA vez; o cabo segue pela placa."""
    perguntas: list[tuple[str, ...]] = []

    def mudo(argv: list[str]) -> str | None:
        perguntas.append(tuple(argv))
        return None

    sysfs = _sysfs(tmp_path, ancoras=0, no_cabo=1)
    lista = ks.controles_do_registro(sysfs, tmp_path / "udev", mudo)
    assert [(c.bus, c.dev) for c in lista] == [(3, 28)], "o cabo tem de seguir pela placa"
    assert perguntas == [("pactl", "list", "sinks")]


def _com_a_conferencia(mesa: _Mesa, responde: str | None) -> list[str]:
    olhados: list[str] = []

    def conferir(no: str) -> str | None:
        olhados.append(no)
        return responde

    mesa.sub._cabo = HapticaDoCabo(lacos=mesa.lacos, conferir=conferir)
    return olhados


def test_o_laco_ligado_a_outro_no_cai_e_nao_se_religa(mesa: _Mesa) -> None:
    """Pedido pelo serial e ligado à fonte padrão: o laço sai, e a rota não volta."""
    olhados = _com_a_conferencia(mesa, "alsa_input.a_fonte_padrao")
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    assert _chave(_P1) in mesa.lacos.vivos
    assert olhados == [], "conferiu na mesma volta que ligou, antes de o grafo ligar"
    mesa.volta(p1)
    assert olhados == [no_de_captura(eh.marca_do_aparelho(_P1))]
    assert _chave(_P1) not in mesa.lacos.vivos, "o laço ficou na fonte errada"
    mesa.volta(p1)
    assert _chave(_P1) not in mesa.lacos.vivos, "a rota que caiu noutro nó se religou"
    assert _do_aparelho(mesa.sysfs, "3-8") in _instancias(mesa.registro())


def test_o_laco_no_endpoint_do_aparelho_se_confere_uma_vez(mesa: _Mesa) -> None:
    """Ligado ao endpoint certo, o laço fica, e o grafo não se lê a cada volta."""
    olhados = _com_a_conferencia(mesa, eh.nome_do_endpoint(_P1))
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    for _ in range(4):
        mesa.volta(p1)
    assert olhados == [no_de_captura(eh.marca_do_aparelho(_P1))]
    assert _chave(_P1) in mesa.lacos.vivos


def _quem_le(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """``(uniq, nó lido, papel)`` de cada gravador que a ponte pede."""
    lidos: list[tuple[str, str, str]] = []

    def _fonte(no: str, **kw: Any) -> tuple[Any, Any, str]:
        lidos.append((str(kw.get("uniq", "")), no, str(kw.get("papel", ""))))
        return (lambda _n: b""), f"gravador:{no}", ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    return lidos


def test_o_no_que_a_ponte_ainda_le_nao_se_reancora_antes_de_ela_descer(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O jogo fecha o fluxo e a âncora do P1 sai, na mesma volta."""
    cinco = _sysfs(tmp_path / "cinco", ancoras=5)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", cinco)
    mesa.sysfs = cinco
    ordem: list[str] = []
    descer = _PonteDeMentira.descer

    def _descer(self: Any, **kw: Any) -> bool:
        ordem.append(f"ponte:{self.uniq}")
        return descer(self, **kw)

    monkeypatch.setattr(_PonteDeMentira, "descer", _descer)
    um = _Controle(_P1, "bt", "/dev/hidraw1")
    nome_do_1 = eh.nome_do_endpoint(_P1)
    mesa.servidor.jogo_em.add(nome_do_1)
    mesa.jogando.add(_P1)
    mesa.volta(um)
    ancora_de_antes = _ancora_do_aparelho(mesa.servidor, _P1)
    servidor = mesa.servidor

    def _pactl(argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "unload-module"]:
            saem = [s["nome"] for s in servidor.sinks.values() if s["mid"] == argv[2]]
            ordem.extend(f"endpoint:{n}" for n in saem)
        return servidor(argv)

    monkeypatch.setattr(af, "_rodar", _pactl)
    servidor.jogo_em.clear()
    ancora_usb = ancora_de_antes.split("/")[-2]
    (cinco / "bus" / "usb" / "devices" / ancora_usb).unlink()
    mesa.volta(um)
    mesa.volta(um)
    assert f"endpoint:{nome_do_1}" in ordem, "o nó da âncora que saiu não se reancorou"
    assert f"ponte:{_P1}" in ordem
    assert ordem.index(f"ponte:{_P1}") < ordem.index(f"endpoint:{nome_do_1}"), ordem
    assert _ancora_do_aparelho(mesa.servidor, _P1) != ancora_de_antes


def test_o_servidor_mudo_nao_derruba_o_laco_do_cabo(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ``pipewire-pulse`` que não responde não é «a placa saiu»."""
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    assert _chave(_P1) in mesa.lacos.vivos
    monkeypatch.setattr(af, "_rodar", lambda _argv: None)
    mesa.volta(p1)
    mesa.volta(p1)
    assert _chave(_P1) in mesa.lacos.vivos, "o laço caiu porque o servidor não respondeu"
    mesa.volta()
    assert _chave(_P1) not in mesa.lacos.vivos, "o laço de quem saiu do cabo ficou"


def test_as_livres_vao_primeiro_a_quem_esta_na_mesa() -> None:
    """A conta pura, pelas marcas: duas âncoras, três aparelhos, um deles na mesa."""
    a, b, c = sorted(eh.marca_do_aparelho(u) for u in (_P1, _P2, _P3))
    duas = [eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in range(2)]
    postas = eh.distribuir_ancoras((a, b, c), duas, ocupados={c})
    assert {m: x.syspath for m, x in postas.items()} == {c: "/d/0", a: "/d/1"}
    postas = eh.distribuir_ancoras((a, b, c), duas, ja_postas={a: duas[0]}, ocupados={c})
    assert {m: x.syspath for m, x in postas.items()} == {a: "/d/0", c: "/d/1"}
    assert eh.distribuir_ancoras((1, 2), duas) == {}  # type: ignore[arg-type]


def test_a_reancoragem_solta_o_laco_antes_do_endpoint(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A âncora do aparelho do P1 saiu: o laço cai ANTES de o endpoint cair."""
    cinco = _sysfs(tmp_path / "cinco", ancoras=5)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", cinco)
    mesa.sysfs = cinco
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    assert _chave(_P1) in mesa.lacos.vivos
    ancora_usb = _ancora_do_aparelho(mesa.servidor, _P1).split("/")[-2]
    ordem: list[str] = []
    desligar = mesa.lacos.desligar
    servidor = mesa.servidor

    def _desligar(chave: str) -> bool:
        caiu = desligar(chave)
        if caiu:
            ordem.append(f"laço:{chave}")
        return caiu

    def _pactl(argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "unload-module"]:
            ordem.append("endpoint")
        return servidor(argv)

    monkeypatch.setattr(mesa.lacos, "desligar", _desligar)
    monkeypatch.setattr(af, "_rodar", _pactl)
    (cinco / "bus" / "usb" / "devices" / ancora_usb).unlink()
    mesa.volta(p1)
    assert "endpoint" in ordem, "o endpoint da âncora que saiu não se reancorou"
    assert ordem[:1] == [f"laço:{_chave(_P1)}"], ordem
    assert _chave(_P1) in mesa.lacos.vivos, "o laço não voltou no endpoint reancorado"


def test_o_stop_solta_os_lacos_do_cabo(mesa: _Mesa) -> None:
    """Os laços morrem com o subsystem, como as pontes."""
    import asyncio

    mesa.volta(_no_cabo(mesa, _P1, 1, "3-8", 28))
    assert _chave(_P1) in mesa.lacos.vivos
    asyncio.run(mesa.sub.stop())
    assert mesa.lacos.vivos == {}


def test_a_placa_sem_os_quatro_canais_nao_ganha_laco(mesa: _Mesa) -> None:
    """Placa de dois canais (o perfil estéreo do ALSA): nada de laço de quatro."""
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.servidor.sinks[mesa.servidor.indice(mesa.placas[_P1])]["canais"] = 2
    mesa.volta(p1)
    assert mesa.lacos.vivos == {}
    assert _do_aparelho(mesa.sysfs, "3-8") in _instancias(mesa.registro())


def test_o_endpoint_nosso_nunca_e_a_placa_do_laco(mesa: _Mesa) -> None:
    """Se a placa que o dono responde for um endpoint desta casa, não há laço."""
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.placas[_P1] = eh.nome_do_endpoint(_P2)
    mesa.volta(p1)
    assert mesa.lacos.vivos == {}
