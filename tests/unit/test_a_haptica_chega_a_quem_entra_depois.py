"""A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01 — o jogo casa o lugar, e não o aparelho.

O registro que o jogo lê (o device KS do prefixo) só se grava no lançamento,
com o ``wineserver`` fora do ar. O endpoint era um por controle no rádio, e no
cabo o bloco levava o ``BUSNUM-DEVNUM`` daquele instante: quem entrava com o
jogo aberto caía num endpoint que o jogo não conhecia. Agora são quatro
endpoints, um por LUGAR, de pé desde o primeiro DualSense; a ponte do rádio lê o
do lugar, e no cabo um laço leva o do lugar à placa.

AS NOVE RÉGUAS DA SPRINT, e cada uma foi vista reprovar com a mordida escrita
nela. Nada aqui toca o servidor de som, o sysfs ou o registro de ninguém: o
servidor é um dublê com estado, o ``/sys`` e o ``system.reg`` moram no
``tmp_path``, e os ``uniq`` são da faixa sintética ``aa:bb:cc``.

LIMITE DECLARADO: é fiação e conta. Se o jogo acha o endpoint que aparece
depois, e o atraso do laço na mão, são a prova no aparelho, e são dela.
"""

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
    chave_do_lugar,
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


# ---------------------------------------------------------------------------
# O /sys de mentira: âncoras (USB sem placa de som) e DualSense no cabo
# ---------------------------------------------------------------------------


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
#: ganham o ``.2``, ``.3`` do PipeWire.
_PLACA = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller"
    "-00{n}.HiFi__Speaker__sink"
)


# ---------------------------------------------------------------------------
# O servidor de som de mentira — com memória, e nunca mais frouxo que o real
# ---------------------------------------------------------------------------


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
        #: índice do sink -> {"nome", "props", "canais", "mid"}
        self.sinks: dict[int, dict[str, Any]] = {}
        #: module_id -> o argumento, como o ``pactl list short modules`` o mostra
        self.modulos: dict[str, str] = {}
        #: índice do fluxo -> {"sink": índice, "nome": node.name}
        self.fluxos: dict[int, dict[str, Any]] = {}
        #: índice do fluxo -> os volumes que o ``set-sink-input-volume`` escreveu
        self.volumes: dict[int, list[str]] = {}
        #: nomes de sink com um fluxo de JOGO tocando
        self.jogo_em: set[str] = set()
        self.cargas: list[str] = []
        self.quedas: list[str] = []
        self._n = 100

    def _proximo(self) -> int:
        self._n += 1
        return self._n

    # -- o estado de partida ---------------------------------------------------

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

    # -- os laços do cabo (o que o `pw-loopback` publica) -----------------------

    def laco_toca(self, chave: str, destino: str) -> None:
        self.fluxos[self._proximo()] = {
            "sink": int(destino), "nome": f"output.hefesto-haptica-do-cabo-{chave}",
        }

    def laco_sai(self, chave: str) -> None:
        self.fluxos = {
            i: f for i, f in self.fluxos.items()
            if f["nome"] != f"output.hefesto-haptica-do-cabo-{chave}"
        }

    def fluxo_do_laco(self, lugar: int) -> int:
        (indice,) = [
            i for i, f in self.fluxos.items()
            if f["nome"] == f"output.hefesto-haptica-do-cabo-{chave_do_lugar(lugar)}"
        ]
        return indice

    # -- as leituras da régua ----------------------------------------------------

    def do_nome(self, nome: str) -> list[dict[str, Any]]:
        return [s for s in self.sinks.values() if s["nome"] == nome]

    def indice(self, nome: str) -> int:
        (achado,) = [i for i, s in self.sinks.items() if s["nome"] == nome]
        return achado

    def nossos(self) -> list[str]:
        return sorted(s["nome"] for s in self.sinks.values() if eh.MARCA_DO_NOME in s["nome"])

    # -- o pactl -----------------------------------------------------------------

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
        self.arranjo = kw.get("arranjo")
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
    #: uniq -> o «Controle N» que o dono responde
    assentos: dict[str, int] = field(default_factory=dict)
    #: uniq -> o nome da placa de som dele (só no cabo)
    placas: dict[str, str] = field(default_factory=dict)
    #: os uniq que mexeram desde que o jogo abriu
    jogando: set[str] = field(default_factory=set)
    #: (nó lido, papel) de cada gravador que a ponte pediu
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
    # A conferência do grafo diz «não sei» aqui: as réguas dela estão no fim.
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


def _ancora_do_lugar(servidor: _Servidor, lugar: int) -> str:
    (no,) = servidor.do_nome(eh.nome_do_endpoint(lugar))
    return str(no["props"]["sysfs.path"])


def _instancias(controles: list[ks.Controle]) -> set[str]:
    """As instâncias ``HEFESTOKS&<bus>&<dev>&<n>`` que o registro ganharia."""
    texto = ks.texto_novo("WINE REGISTRY Version 2\n", controles, 1)
    return set(re.findall(r"HEFESTOKS&\d{3}&\d{3}&\d", texto))


def _do_aparelho(sysfs: Path, nome: str) -> str:
    devnum = int((sysfs / "bus" / "usb" / "devices" / nome / "devnum").read_text())
    return f"HEFESTOKS&003&{devnum:03d}&0"


# ---------------------------------------------------------------------------
# 1. O lugar: o bloco do P4 existe antes de o P4 chegar
# ---------------------------------------------------------------------------


def test_o_bloco_do_lugar_4_existe_antes_de_o_p4_chegar(mesa: _Mesa) -> None:
    """Três no lançamento, o quarto depois: o jogo já conhece o lugar dele.

    MORDIDA: em ``AltoFalanteSubsystem._lugares_de_pe``, devolva só os lugares
    ocupados (``tuple(sorted(set(...)))`` dos lugares da mesa) — a lista volta
    a ser só os presentes, e o bloco do lugar 4 não nasce.
    """
    mesa.assentos.update({_P1: 1, _P2: 2, _P3: 3})
    mesa.volta(*(_Controle(u, "bt") for u in (_P1, _P2, _P3)))
    lancamento = mesa.registro()
    assert len(lancamento) == 4, f"o registro do lançamento tem {len(lancamento)} lugar(es)"
    do_lugar_4 = _do_aparelho(mesa.sysfs, "3-4")
    assert do_lugar_4 in _instancias(lancamento), "o P4 que entrar depois não terá bloco"
    assert _ancora_do_lugar(mesa.servidor, 4).startswith("/devices/pci0000:00/usb3/3-4/")


# ---------------------------------------------------------------------------
# 2. O nome não é o endereço
# ---------------------------------------------------------------------------


def test_um_controle_sobe_os_quatro_lugares_sem_endereco_no_nome(mesa: _Mesa) -> None:
    """Com um só na mesa, quatro endpoints de nomes distintos e nenhum hex do ``uniq``.

    MORDIDA: troque ``MOLDE_DA_MARCA_DO_LUGAR`` por seis dígitos
    (``"{lugar}{lugar}{lugar}{lugar}{lugar}{lugar}"``) — o nome ganha a forma de
    endereço que as réguas de forma leem como o rabo de um controle.
    """
    mesa.assentos[_P3] = 1
    mesa.volta(_Controle(_P3, "bt"))
    nomes = mesa.servidor.nossos()
    assert nomes == sorted(eh.nome_do_endpoint(n) for n in eh.LUGARES)
    assert len(set(nomes)) == 4
    for nome in nomes:
        assert eh.marca_do_controle(_P3) not in nome.lower()
        assert not re.search(r"HEFESTO[0-9A-Fa-f]{6}(?![0-9A-Fa-f])", nome), nome
        assert all(agulha in nome for agulha in eh.AGULHAS)


# ---------------------------------------------------------------------------
# 3. Quem entra não cria nó
# ---------------------------------------------------------------------------


def test_o_p4_que_entra_com_o_jogo_aberto_le_o_endpoint_que_ja_existia(mesa: _Mesa) -> None:
    """Jogo aberto com três; o P4 liga pelo BT e a ponte lê o endpoint 4 de antes.

    MORDIDA: a mesma da régua 1 (só os lugares ocupados de pé) — o endpoint 4
    passa a nascer NA CHEGADA, com o jogo aberto, e o jogo não o conhece.
    """
    tres = [_Controle(u, "bt", f"/dev/hidraw{i}") for i, u in enumerate((_P1, _P2, _P3), 1)]
    mesa.assentos.update({_P1: 1, _P2: 2, _P3: 3, _P4: 4})
    mesa.volta(*tres)
    mesa.servidor.jogo_em.update(eh.nome_do_endpoint(n) for n in eh.LUGARES)
    mesa.jogando.add(_P4)
    cargas = list(mesa.servidor.cargas)
    mesa.volta(*tres, _Controle(_P4, "bt", "/dev/hidraw4"))
    assert mesa.servidor.cargas == cargas, "o P4 fez nascer um nó com o jogo aberto"
    assert mesa.servidor.quedas == []
    assert (eh.nome_do_endpoint(4), "haptica") in mesa.lidos
    (ponte_do_p4,) = [p for p in _PonteDeMentira.criadas if p.uniq == _P4]
    assert ponte_do_p4.arranjo is af.ARRANJO_HAPTICA_032


# ---------------------------------------------------------------------------
# Por controle: as 24 ordens de conexão, cabo e BT misturados
# ---------------------------------------------------------------------------

#: O lugar de cada um, e o aparelho dos dois que chegam pelo cabo.
_LUGAR = {_P1: 1, _P2: 2, _P3: 3, _P4: 4}
_NO_CABO = {_P1: ("3-8", 28), _P2: ("3-7", 29)}
_ORDENS = list(itertools.permutations((_P1, _P2, _P3, _P4)))


@pytest.mark.parametrize(
    "ordem", _ORDENS, ids=["".join(u[-1] for u in o) for o in _ORDENS]
)
def test_em_qualquer_ordem_quem_chega_cai_no_lugar_que_ja_existia(
    mesa: _Mesa, ordem: tuple[str, ...]
) -> None:
    """O critério «por controle» da sprint: os quatro lugares, nas 24 ordens.

    P1 e P2 chegam pelo cabo, P3 e P4 pelo rádio, em cada uma das 24 ordens.
    Depois da primeira chegada, ninguém faz nascer nó, nenhum nó cai, e a
    lista que o registro grava não muda — é a mesma do lançamento, com quem
    chegar depois. No fim, os dois do cabo têm laço, e só eles.

    MORDIDA: a da régua 1 (só os lugares ocupados de pé) — cada chegada passa
    a carregar o nó do lugar, e o registro muda a cada uma.
    """
    chegaram: list[_Controle] = []
    cargas: list[Any] | None = None
    blocos: set[str] | None = None
    for uniq in ordem:
        if uniq in _NO_CABO:
            aparelho, devnum = _NO_CABO[uniq]
            chegaram.append(_no_cabo(mesa, uniq, _LUGAR[uniq], aparelho, devnum))
        else:
            mesa.assentos[uniq] = _LUGAR[uniq]
            chegaram.append(_Controle(uniq, "bt", f"/dev/hidraw{_LUGAR[uniq]}"))
        mesa.volta(*chegaram)
        assert mesa.servidor.nossos() == sorted(eh.nome_do_endpoint(n) for n in eh.LUGARES)
        agora = _instancias(mesa.registro())
        if cargas is None or blocos is None:
            cargas, blocos = list(mesa.servidor.cargas), agora
        assert mesa.servidor.cargas == cargas, f"a chegada de {uniq} fez nascer um nó"
        assert agora == blocos, f"a lista do registro mudou quando {uniq} chegou"
    assert len(blocos or ()) == 4
    assert mesa.servidor.quedas == []
    assert set(mesa.lacos.vivos) == {chave_do_lugar(1), chave_do_lugar(2)}


# ---------------------------------------------------------------------------
# 4. O replug do cabo
# ---------------------------------------------------------------------------


def _no_cabo(mesa: _Mesa, uniq: str, lugar: int, aparelho: str, devnum: int) -> _Controle:
    """Um DualSense no cabo: o aparelho no ``/sys``, a placa no servidor e o lugar."""
    if not (mesa.sysfs / "bus" / "usb" / "devices" / aparelho).exists():
        _aparelho(mesa.sysfs, aparelho, vid="054c", pid="0ce6", devnum=devnum, placa=True)
    placa = _PLACA.format(n="" if lugar == 1 else f".{lugar}")
    mesa.servidor.placa(placa, _caminho_da_placa(aparelho))
    mesa.placas[uniq] = placa
    mesa.assentos[uniq] = lugar
    return _Controle(uniq, "usb")


def test_o_replug_nao_muda_o_lugar_e_o_laco_segue_a_placa_nova(mesa: _Mesa) -> None:
    """O P1 volta com ``DEVNUM`` novo: o endpoint e o bloco do lugar 1 ficam.

    MORDIDA: em ``controles_do_registro``, devolva ``controles_no_cabo(...) +
    lugares`` sem tirar as placas servidas — o bloco volta a ser pelo
    ``BUSNUM-DEVNUM``, e o replug o troca.
    """
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    antes = mesa.registro()
    ancora = _ancora_do_lugar(mesa.servidor, 1)
    (primeira,) = [lig for lig in mesa.lacos.ligacoes if lig[0] == chave_do_lugar(1)]
    # O cabo sai e volta: outro DEVNUM, e o ALSA publica a placa de novo.
    velha = mesa.placas[_P1]
    mesa.servidor.sinks = {i: s for i, s in mesa.servidor.sinks.items() if s["nome"] != velha}
    (mesa.sysfs / "bus" / "usb" / "devices" / "3-8" / "devnum").write_text("41\n")
    nova = _PLACA.format(n=".9")
    mesa.servidor.placa(nova, _caminho_da_placa("3-8"))
    mesa.placas[_P1] = nova
    mesa.volta(p1)
    assert _ancora_do_lugar(mesa.servidor, 1) == ancora
    assert mesa.servidor.quedas == [], "o endpoint do lugar caiu com o replug"
    ultima = [lig for lig in mesa.lacos.ligacoes if lig[0] == chave_do_lugar(1)][-1]
    assert ultima[2] == str(mesa.servidor.indice(nova)) != primeira[2], "o laço não seguiu a placa"
    depois = mesa.registro()
    assert _instancias(depois) == _instancias(antes), "o bloco do lugar 1 mudou com o replug"
    assert "HEFESTOKS&003&041&0" not in _instancias(depois)


# ---------------------------------------------------------------------------
# 5. Um alvo por controle
# ---------------------------------------------------------------------------


def test_o_cabo_com_lugar_ancorado_nao_tem_bloco_proprio(mesa: _Mesa) -> None:
    """A placa e o lugar seriam dois alvos para o mesmo controle.

    MORDIDA: em ``controles_do_registro``, mantenha o ``controles_no_cabo`` na
    lista (``servidas = set()``).
    """
    mesa.volta(_no_cabo(mesa, _P1, 1, "3-8", 28))
    instancias = _instancias(mesa.registro())
    assert _do_aparelho(mesa.sysfs, "3-8") not in instancias, (
        "o P1 tem bloco pela placa E pelo lugar"
    )
    assert len(instancias) == 4


# ---------------------------------------------------------------------------
# 6. A (b) no cabo
# ---------------------------------------------------------------------------


def test_so_quem_mexeu_vibra_no_cabo_e_o_alto_falante_passa_nos_dois(mesa: _Mesa) -> None:
    """Dois no cabo, o mesmo sinal nos endpoints 1 e 2, e só o P2 mexeu.

    MORDIDA: em ``_casar_o_cabo``, abra o portão de todo laço
    (``abertos.add(lugar)`` fora do ``if este_joga``).
    """
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    p2 = _no_cabo(mesa, _P2, 2, "3-7", 29)
    mesa.servidor.jogo_em.update({eh.nome_do_endpoint(1), eh.nome_do_endpoint(2)})
    mesa.jogando.add(_P2)
    mesa.volta(p1, p2)
    um = mesa.servidor.volumes[mesa.servidor.fluxo_do_laco(1)]
    dois = mesa.servidor.volumes[mesa.servidor.fluxo_do_laco(2)]
    assert um == ["100%", "100%", "0%", "0%"], f"o P1 parado vibrou: {um}"
    assert dois == ["100%", "100%", "100%", "100%"], f"o P2 na mão não vibrou: {dois}"
    for _chave, captura, destino, canais, mapa in mesa.lacos.ligacoes:
        assert (canais, mapa) == (4, MAPA), "o laço não leva os quatro canais um a um"
        assert captura.isdigit() and destino.isdigit(), "o laço pelo nome cai na fonte padrão"
    assert {lig[1] for lig in mesa.lacos.ligacoes} == {
        str(mesa.servidor.indice(eh.nome_do_endpoint(n))) for n in (1, 2)
    }


# ---------------------------------------------------------------------------
# 7. A guarda do Black Desert pergunta pelo controle, e não pelo endpoint
# ---------------------------------------------------------------------------


def _lancar(tmp_path: Path, sysfs: Path) -> str:
    """Roda o wrapper com a opção ligada pelo daemon; devolve o que o jogo viu.

    O ``pactl`` de mentira responde que os QUATRO lugares estão de pé — o
    estado em que a sonda de antes dizia "há endpoint" sem controle nenhum.
    """
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
        f"{n}\\t{eh.nome_do_endpoint(n)}\\tPipeWire\\tfloat32le 4ch 48000Hz\\tIDLE"
        for n in eh.LUGARES
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


def test_os_lugares_de_pe_sem_dualsense_na_mesa_deixam_a_opcao_em_zero(tmp_path: Path) -> None:
    """Os quatro endpoints de pé e nenhum DualSense físico: o Black Desert fica salvo.

    MORDIDA: faça ``dualsense_fisico_na_mesa`` perguntar pelo endpoint
    (``dualsense_no_cabo || pactl list short sinks | grep -q HEFESTO``) — os
    lugares respondem «há», e a opção liga sem controle nenhum.
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
    (hid / "0003:054C:0DF2.0009").mkdir()  # o vpad do produto: não conta
    assert _lancar(tmp_path / "so-o-vpad", sysfs) == "0"
    (hid / "0005:054C:0CE6.0004").mkdir()
    assert _lancar(tmp_path / "com-o-radio", sysfs) == "1"


# ---------------------------------------------------------------------------
# 8. O lugar sem âncora: o cabo segue pela placa, e o doctor diz
# ---------------------------------------------------------------------------


def test_o_lugar_sem_ancora_deixa_o_cabo_na_placa(
    monkeypatch: pytest.MonkeyPatch, mesa: _Mesa, tmp_path: Path
) -> None:
    """Uma âncora e dois no cabo: o lugar 1 pelo endpoint, o P2 pelo ``BUSNUM-DEVNUM``.

    MORDIDA: em ``controles_do_registro``, tire o cabo da lista (``cabo = []``)
    — sem o recuo, o controle do lugar 2 fica sem bloco nenhum.
    """
    uma = _sysfs(tmp_path / "uma", ancoras=1)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", uma)
    mesa.sysfs = uma
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    p2 = _no_cabo(mesa, _P2, 2, "3-7", 29)
    mesa.volta(p1, p2)
    assert mesa.servidor.nossos() == [eh.nome_do_endpoint(1)]
    assert set(mesa.lacos.vivos) == {chave_do_lugar(1)}, "o lugar sem âncora ganhou laço"
    instancias = _instancias(mesa.registro())
    assert _do_aparelho(uma, "3-7") in instancias, "o controle do lugar 2 ficou sem bloco"
    assert _do_aparelho(uma, "3-8") not in instancias, "o P1 tem dois alvos"
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
    """Dois na mesa e uma âncora: «1 lugar(es) sem âncora».

    MORDIDA: troque o ``em_uso`` da comparação por ``lugares`` — o doctor
    passa a dizer três, contando lugares que ninguém ocupa como falta.
    """
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


# ---------------------------------------------------------------------------
# 9. O órfão de nome velho
# ---------------------------------------------------------------------------


def test_o_endpoint_de_nome_por_endereco_cai_na_primeira_volta(mesa: _Mesa) -> None:
    """O servidor com os endpoints por controle do processo de antes do install.

    MORDIDA: em ``_modulos_desta_casa``, pule a linha que não traz a marca do
    lugar (``if "HEFESTOLUGAR" not in linha: continue``) — o varredor passa a
    conhecer só o nome novo, e o de antes fica na lista de som dela.
    """
    velhos = [
        mesa.servidor.modulo_herdado(eh.MOLDE_DO_NOME.format(marca=f"0000c{n}"), f"/d/{n}/i:1.0")
        for n in (3, 4)
    ]
    mesa.assentos[_P3] = 1
    mesa.volta(_Controle(_P3, "bt"))
    assert set(velhos) <= set(mesa.servidor.quedas), "o endpoint de nome velho ficou de pé"
    assert mesa.servidor.nossos() == sorted(eh.nome_do_endpoint(n) for n in eh.LUGARES)


def test_o_endpoint_do_ensaio_nao_e_orfao(mesa: _Mesa) -> None:
    """O nó que a bancada montou pelo ensaio não é resto de processo nenhum."""
    props = " ".join(f"{k}={v}" for k, v in _SONY.items())
    mesa.servidor(["pactl", "load-module", "module-null-sink",
                   f"sink_name={eh.MOLDE_DO_NOME.format(marca='0000c9')}", "channels=4",
                   f'sink_properties="{props} sysfs.path=/d/9/i:1.0 {eh.MARCA_DO_ENSAIO}"'])
    mesa.assentos[_P3] = 1
    mesa.volta(_Controle(_P3, "bt"))
    assert mesa.servidor.quedas == []


# ---------------------------------------------------------------------------
# E o que o sistema faz sem a mesa: os lugares caem, menos com o jogo tocando
# ---------------------------------------------------------------------------


def test_sem_dualsense_os_lugares_caem_e_o_jogo_tocando_os_segura(mesa: _Mesa) -> None:
    """Os quatro ficam enquanto houver DualSense ou jogo com fluxo num deles."""
    mesa.assentos[_P3] = 1
    mesa.volta(_Controle(_P3, "bt"))
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(2))
    mesa.volta()
    assert len(mesa.servidor.nossos()) == 4, "o nó sumiu debaixo do jogo"
    mesa.servidor.jogo_em.clear()
    mesa.volta()
    assert mesa.servidor.nossos() == []


def test_o_laco_cai_antes_do_endpoint_do_lugar(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O laço cujo alvo some pode ser religado à fonte padrão: ele sai primeiro.

    MORDIDA: tire o ``self._o_cabo().soltar(lugar)`` de antes do
    ``endpoint.parar()`` em ``_casar_as_pontes`` — o nó cai com o laço lendo.
    """
    mesa.volta(_no_cabo(mesa, _P1, 1, "3-8", 28))
    assert chave_do_lugar(1) in mesa.lacos.vivos
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
    assert ordem[:1] == [f"laço:{chave_do_lugar(1)}"], ordem
    assert "endpoint" in ordem


# ---------------------------------------------------------------------------
# O dono da lista pergunta pouco: o curador roda dentro do lançamento
# ---------------------------------------------------------------------------


def test_sem_cabo_o_dono_da_lista_nao_pergunta_pelos_fluxos(tmp_path: Path) -> None:
    """Quem joga pelo rádio paga UMA ida ao servidor no lançamento, e não duas.

    MORDIDA: pergunte `placas_servidas` sempre, antes de saber se há cabo — a
    pergunta dos fluxos aparece na lista.
    """
    perguntas: list[tuple[str, ...]] = []

    def servidor(argv: list[str]) -> str | None:
        perguntas.append(tuple(argv))
        return ""

    sysfs = _sysfs(tmp_path, ancoras=1)
    assert ks.controles_do_registro(sysfs, tmp_path / "udev", servidor) == []
    assert perguntas == [("pactl", "list", "sinks")]


def test_o_servidor_mudo_cala_a_segunda_pergunta(tmp_path: Path) -> None:
    """O `pactl` que não responde é perguntado UMA vez; o cabo segue pela placa.

    O curador tem dez segundos no gancho e cada `pactl`, cinco: duas perguntas
    a um servidor travado estourariam o teto e o lançamento esperaria à toa.

    MORDIDA: tire o `_lembrando` de `controles_do_registro` — a pergunta dos
    fluxos vai ao servidor mudo, e a lista das perguntas cresce.
    """
    perguntas: list[tuple[str, ...]] = []

    def mudo(argv: list[str]) -> str | None:
        perguntas.append(tuple(argv))
        return None

    sysfs = _sysfs(tmp_path, ancoras=0, no_cabo=1)
    lista = ks.controles_do_registro(sysfs, tmp_path / "udev", mudo)
    assert [(c.bus, c.dev) for c in lista] == [(3, 28)], "o cabo tem de seguir pela placa"
    assert perguntas == [("pactl", "list", "sinks")]


# ---------------------------------------------------------------------------
# A outra metade da SOM-ECO-02: o laço que pediu o endpoint e caiu noutro nó
# ---------------------------------------------------------------------------


def _com_a_conferencia(mesa: _Mesa, responde: str | None) -> list[str]:
    olhados: list[str] = []

    def conferir(no: str) -> str | None:
        olhados.append(no)
        return responde

    mesa.sub._cabo = HapticaDoCabo(lacos=mesa.lacos, conferir=conferir)
    return olhados


def test_o_laco_ligado_a_outro_no_cai_e_nao_se_religa(mesa: _Mesa) -> None:
    """Pedido pelo serial e ligado à fonte padrão: o laço sai, e a rota não volta.

    A fonte padrão desta máquina é o microfone do controle; um laço ligado a
    ela mandaria a voz dela ao alto-falante da placa. Sem o laço, o registro
    devolve ao controle o bloco da placa, que é o caminho que já vibrava.

    MORDIDA: em ``HapticaDoCabo._conferir``, tire o ``self.soltar(lugar)`` do
    ramo do nó errado — o laço fica de pé, lendo a fonte errada.
    """
    olhados = _com_a_conferencia(mesa, "alsa_input.a_fonte_padrao")
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    assert chave_do_lugar(1) in mesa.lacos.vivos
    assert olhados == [], "conferiu na mesma volta que ligou, antes de o grafo ligar"
    mesa.volta(p1)
    assert olhados == [no_de_captura(1)]
    assert chave_do_lugar(1) not in mesa.lacos.vivos, "o laço ficou na fonte errada"
    mesa.volta(p1)
    assert chave_do_lugar(1) not in mesa.lacos.vivos, "a rota que caiu noutro nó se religou"
    assert _do_aparelho(mesa.sysfs, "3-8") in _instancias(mesa.registro())


def test_o_laco_no_endpoint_do_lugar_se_confere_uma_vez(mesa: _Mesa) -> None:
    """Ligado ao endpoint certo, o laço fica, e o grafo não se lê a cada volta.

    MORDIDA: tire o ``self._conferidos.add(lugar)`` — a conferência passa a
    ler o grafo inteiro a cada volta do daemon.
    """
    olhados = _com_a_conferencia(mesa, eh.nome_do_endpoint(1))
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    for _ in range(4):
        mesa.volta(p1)
    assert olhados == [no_de_captura(1)]
    assert chave_do_lugar(1) in mesa.lacos.vivos


# ---------------------------------------------------------------------------
# A conferência de 28/09: o lugar que anda troca a ponte, o «não sei» do
# servidor não derruba o laço, e quem está sentado vem primeiro nas âncoras
# ---------------------------------------------------------------------------


def _quem_le(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """``(uniq, nó lido, papel)`` de cada gravador que a ponte pede."""
    lidos: list[tuple[str, str, str]] = []

    def _fonte(no: str, **kw: Any) -> tuple[Any, Any, str]:
        lidos.append((str(kw.get("uniq", "")), no, str(kw.get("papel", ""))))
        return (lambda _n: b""), f"gravador:{no}", ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    return lidos


def test_o_lugar_que_anda_troca_a_ponte_de_endpoint(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P1 e P2 no rádio trocam de lugar com o jogo aberto: cada ponte passa a ler o do lugar novo.

    É a metade do «o número que anda troca o laço ou a ponte» que o cabo já
    fazia (a rota do laço muda com o endpoint) e a ponte não: ela só descia
    quando o MODO mudava, e seguia lendo o endpoint do lugar de antes — o
    controle vibrava pelo jogador que se sentou ali.

    MORDIDA: em ``_casar_as_pontes``, volte a comparar só o modo
    (``if self._modo_da_ponte.get(uniq) == modo: continue``) — as duas pontes
    ficam de pé lendo o endpoint trocado.
    """
    lidos = _quem_le(monkeypatch)
    um, dois = _Controle(_P1, "bt", "/dev/hidraw1"), _Controle(_P2, "bt", "/dev/hidraw2")
    mesa.assentos.update({_P1: 1, _P2: 2})
    mesa.servidor.jogo_em.update({eh.nome_do_endpoint(1), eh.nome_do_endpoint(2)})
    mesa.jogando.update({_P1, _P2})
    mesa.volta(um, dois)
    assert (_P1, eh.nome_do_endpoint(1), "haptica") in lidos
    assert (_P2, eh.nome_do_endpoint(2), "haptica") in lidos
    lidos.clear()
    mesa.assentos.update({_P1: 2, _P2: 1})
    mesa.volta(um, dois)
    assert (_P1, eh.nome_do_endpoint(2), "haptica") in lidos, "o P1 segue lendo o lugar de antes"
    assert (_P2, eh.nome_do_endpoint(1), "haptica") in lidos, "o P2 segue lendo o lugar de antes"
    assert mesa.servidor.quedas == [], "o lugar que anda derrubou um endpoint"
    lidos.clear()
    mesa.volta(um, dois)
    assert lidos == [], "a ponte que já lê o lugar certo desceu e subiu à toa"


def test_o_no_que_a_ponte_ainda_le_nao_se_reancora_antes_da_troca(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O controle mudou de lugar e a âncora do lugar de antes saiu, na mesma volta.

    A reancoragem roda antes da troca de ponte: se ela derrubasse o endpoint
    que a ponte ainda lê, o gravador cairia na fonte padrão (SOM-ECO-02). A
    ponte desce primeiro; o nó se reancora na volta seguinte.

    MORDIDA: tire o ``atual.nome in lido`` da guarda da reancoragem — o nó do
    lugar 1 cai com a ponte do P1 ainda lendo.
    """
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
    mesa.assentos[_P1] = 1
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(1))
    mesa.jogando.add(_P1)
    mesa.volta(um)
    ancora_de_antes = _ancora_do_lugar(mesa.servidor, 1)
    servidor = mesa.servidor
    nome_do_1 = eh.nome_do_endpoint(1)

    def _pactl(argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "unload-module"]:
            saem = [s["nome"] for s in servidor.sinks.values() if s["mid"] == argv[2]]
            ordem.extend(f"endpoint:{n}" for n in saem)
        return servidor(argv)

    monkeypatch.setattr(af, "_rodar", _pactl)
    # O jogo fecha o fluxo, o P1 vai para o lugar 2 e o aparelho da âncora do 1 sai.
    servidor.jogo_em.clear()
    (cinco / "bus" / "usb" / "devices" / "3-1").unlink()
    mesa.assentos[_P1] = 2
    mesa.volta(um)
    mesa.volta(um)
    assert f"endpoint:{nome_do_1}" in ordem, "o nó da âncora que saiu não se reancorou"
    assert f"ponte:{_P1}" in ordem
    assert ordem.index(f"ponte:{_P1}") < ordem.index(f"endpoint:{nome_do_1}"), ordem
    assert _ancora_do_lugar(mesa.servidor, 1) != ancora_de_antes


def test_o_servidor_mudo_nao_derruba_o_laco_do_cabo(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ``pipewire-pulse`` que não responde não é «a placa saiu».

    O laço é um processo do PipeWire, e não depende do ``pactl``: com o
    servidor mudo (a queda de um controle pelo rádio já o deixou horas assim),
    o cabo seguia vibrando antes desta leva, e tem de seguir. Quem sai do cabo
    leva o laço mesmo assim — isso o ``/sys`` diz sem o servidor.

    MORDIDA: em ``_casar_as_pontes``, devolva ``motores = lidos`` sem olhar se
    houve resposta — a lista vazia do servidor mudo derruba o laço.
    """
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    assert chave_do_lugar(1) in mesa.lacos.vivos
    monkeypatch.setattr(af, "_rodar", lambda _argv: None)
    mesa.volta(p1)
    mesa.volta(p1)
    assert chave_do_lugar(1) in mesa.lacos.vivos, "o laço caiu porque o servidor não respondeu"
    mesa.volta()
    assert chave_do_lugar(1) not in mesa.lacos.vivos, "o laço de quem saiu do cabo ficou"


def test_com_uma_ancora_o_controle_sozinho_no_lugar_2_fica_com_ela(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Um notebook com uma âncora e um DualSense só, que é o «Controle 2».

    Antes desta leva o endpoint era do controle, e a âncora era dele. Por
    lugar, na ordem pura, ela ia ao lugar 1 vazio e o controle ficava sem
    vibração pelo rádio.

    MORDIDA: em ``distribuir_ancoras``, sirva as livres só em ordem de lugar
    (sem os ``ocupados`` primeiro).
    """
    uma = _sysfs(tmp_path / "uma", ancoras=1)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", uma)
    mesa.sysfs = uma
    lidos = _quem_le(monkeypatch)
    mesa.assentos[_P2] = 2
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(2))
    mesa.jogando.add(_P2)
    mesa.volta(_Controle(_P2, "bt", "/dev/hidraw2"))
    assert mesa.servidor.nossos() == [eh.nome_do_endpoint(2)]
    assert (_P2, eh.nome_do_endpoint(2), "haptica") in lidos


def test_as_livres_vao_primeiro_a_quem_esta_sentado() -> None:
    """A conta pura: duas âncoras, o lugar 3 ocupado — o 3 e depois o 1."""
    duas = [eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in range(2)]
    postas = eh.distribuir_ancoras(eh.LUGARES, duas, ocupados={3})
    assert {n: a.syspath for n, a in postas.items()} == {3: "/d/0", 1: "/d/1"}
    # A posse não muda: quem já tem âncora fica com ela, ocupado ou não.
    postas = eh.distribuir_ancoras(eh.LUGARES, duas, ja_postas={1: duas[0]}, ocupados={3})
    assert {n: a.syspath for n, a in postas.items()} == {1: "/d/0", 3: "/d/1"}


def test_a_reancoragem_solta_o_laco_antes_do_endpoint(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A âncora do lugar do P1 saiu: o laço cai ANTES de o endpoint cair.

    O laço cujo alvo some pode ser religado à fonte padrão (SOM-ECO-02), e a
    reancoragem derruba o endpoint do lugar como a saída da mesa derruba.

    MORDIDA: tire o ``self._o_cabo().soltar(lugar)`` do ramo da reancoragem.
    """
    cinco = _sysfs(tmp_path / "cinco", ancoras=5)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", cinco)
    mesa.sysfs = cinco
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.volta(p1)
    assert chave_do_lugar(1) in mesa.lacos.vivos
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
    (cinco / "bus" / "usb" / "devices" / "3-1").unlink()
    mesa.volta(p1)
    assert "endpoint" in ordem, "o endpoint da âncora que saiu não se reancorou"
    assert ordem[:1] == [f"laço:{chave_do_lugar(1)}"], ordem
    assert chave_do_lugar(1) in mesa.lacos.vivos, "o laço não voltou no endpoint reancorado"


def test_o_stop_solta_os_lacos_do_cabo(mesa: _Mesa) -> None:
    """Os laços morrem com o subsystem, como as pontes.

    MORDIDA: tire o ``cabo.parar`` do ``stop()`` — o ``pw-loopback`` fica de pé
    depois do subsystem parado, e o próximo ``start()`` abriria outro.
    """
    import asyncio

    mesa.volta(_no_cabo(mesa, _P1, 1, "3-8", 28))
    assert chave_do_lugar(1) in mesa.lacos.vivos
    asyncio.run(mesa.sub.stop())
    assert mesa.lacos.vivos == {}


def test_a_placa_sem_os_quatro_canais_nao_ganha_laco(mesa: _Mesa) -> None:
    """Placa de dois canais (o perfil estéreo do ALSA): nada de laço de quatro.

    Um laço de quatro canais numa placa de dois faria o PipeWire misturar os
    motores no alto-falante. O controle segue pela placa, com o bloco dele.

    MORDIDA: tire o ``placa not in placas`` de ``_casar_o_cabo``.
    """
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.servidor.sinks[mesa.servidor.indice(mesa.placas[_P1])]["canais"] = 2
    mesa.volta(p1)
    assert mesa.lacos.vivos == {}
    assert _do_aparelho(mesa.sysfs, "3-8") in _instancias(mesa.registro())


def test_o_endpoint_nosso_nunca_e_a_placa_do_laco(mesa: _Mesa) -> None:
    """Se a placa que o dono responde for um endpoint desta casa, não há laço.

    MORDIDA: tire o ``MARCA_DO_NOME in placa`` de ``_casar_o_cabo`` — o lugar
    1 passa a tocar no endpoint do lugar 2.
    """
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    mesa.placas[_P1] = eh.nome_do_endpoint(2)
    mesa.volta(p1)
    assert mesa.lacos.vivos == {}


def test_quem_o_dono_nao_numera_fica_no_lugar_de_antes(mesa: _Mesa) -> None:
    """O numerador pisca (sem daemon por um instante): o controle não pula de lugar.

    MORDIDA: tire o segundo passo de ``_lugares_da_mesa`` (o lugar da volta
    anterior) — o P3 cai no primeiro lugar livre, o 2.
    """
    um, tres = _Controle(_P1, "bt", "/dev/hidraw1"), _Controle(_P3, "bt", "/dev/hidraw3")
    mesa.assentos.update({_P1: 1, _P3: 3})
    mesa.volta(um, tres)
    mesa.assentos[_P3] = None  # type: ignore[assignment]
    mesa.volta(um, tres)
    assert mesa.sub._endpoint_de(_P3).nome == eh.nome_do_endpoint(3)


def test_dois_com_o_mesmo_numero_nao_dividem_o_lugar(mesa: _Mesa) -> None:
    """O dono responde o mesmo número para dois: um fica com ele, o outro vai ao livre.

    MORDIDA: tire o ``numero not in tomados`` do primeiro passo de
    ``_lugares_da_mesa`` — os dois leem o mesmo endpoint.
    """
    um, dois = _Controle(_P1, "bt", "/dev/hidraw1"), _Controle(_P2, "bt", "/dev/hidraw2")
    mesa.assentos.update({_P1: 1, _P2: 1})
    mesa.volta(um, dois)
    assert mesa.sub._endpoint_de(_P1).nome == eh.nome_do_endpoint(1)
    assert mesa.sub._endpoint_de(_P2).nome == eh.nome_do_endpoint(2)
