"""O-BROKER-NAO-REESCREVE-O-QUE-NAO-MUDOU-01 — o broker só escreve no nó que mudou.

O ACHADO (25/09/2026, medido na máquina dela, só lendo): a cada 30 s o daemon
pede ao broker que re-esconda o hidraw físico e os nós de entrada de cada
DualSense (o rehide da reconciliação), e o broker fazia `removexattr` da ACL e
`chmod 0600` em cada nó SEM olhar o estado. Com quatro controles pelo rádio,
20 nós por volta: o `ctime` andava a cada 30 s e cada volta disparava de 20 a
40 `IN_ATTRIB` para quem vigia `/dev` e `/dev/input` — de 57.600 a 115.200 por
dia, e o diário do broker sem linha nenhuma deles.

A CURA é uma pergunta só, nos quatro escritores de nó do broker (`hide`,
`restore`, `fechar_entradas`, `abrir_entradas`): *o nó pinado já está como a
escrita o deixaria?* E a vigia do sequestro, que dependia do `ctime` andar a
cada 30 s, passa a não confiar na morte do dono (R5).

A MESA DE MENTIRA é a da `test_o_no_do_nativo_nao_fica_exposto.py`: o
`BrokerState`, o `FsAclOps` e o validador são os de produção, pedidos pelo
`handle_line`. A única troca é «é char device?», que aceita arquivo comum — a
suíte não cria char device sem root. Nada aqui toca `/dev`, o sysfs real, o
broker vivo ou o daemon.

Quatro DualSense, de um a quatro jogadores e nos dois transportes: dois 0ce6
pelo rádio sob o uhid, um 0ce6 pelo cabo, e o Edge (0df2) pelo cabo com pai USB
de verdade. Cada um tem o hidraw, o event do gamepad, do movimento e do
touchpad, o js do gamepad, a tomada do fone quando é pelo cabo, e o js do
movimento — este fora do alcance do broker (a regra 80). São 22 nós no
alcance. E o nosso vpad, que o validador recusa.

O INSTRUMENTO é o da medição: um `inotify` nos diretórios `dev/` e `dev/input/`
da mesa, lido depois de CADA volta (o evento entra na fila antes de a syscall
voltar). Ele conta `IN_ATTRIB`, e não o `ctime`, porque no ext4 do `/tmp` o
`removexattr` sem ACL não anda o `ctime` (medido em 25/09). O `ctime` é
conferido onde a pergunta é da vigia (R4 e R5), que lê a firma real.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import stat
import struct
import time
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import (
    BrokerState,
    FsAclOps,
    decode_acl_user_uids,
    encode_access_acl,
)
from hefesto_dualsense4unix.core import escritor_cru as ec

UID = os.getuid()
ACL = "system.posix_acl_access"
#: Faixas sintéticas da casa para fixture: nunca endereço real mascarado.
MAC_DO_ADAPTADOR = "aa:bb:cc:00:00:01"

#: (jogador, hidraw, transporte, HID_ID do pai, MAC do controle). O número do
#: hidraw é o prefixo dos nós de entrada dele, só para quem lê se achar.
CONTROLES = (
    ("P1", "hidraw3", "radio", "0005:054C:0CE6.0003", "e8:47:3a:00:00:03"),
    ("P2", "hidraw5", "radio", "0005:054C:0CE6.0005", "e8:47:3a:00:00:05"),
    ("P3", "hidraw7", "cabo", "0003:054C:0CE6.0007", ""),
    ("P4", "hidraw9", "cabo", "0003:054C:0DF2.0009", ""),  # o Edge
)
JOGADORES = tuple(c[0] for c in CONTROLES)
#: As voltas da R2 (e os rehides da R4) em que alguém mexe num nó.
VOLTA_DA_REGRA_QUE_REABRE = 17
VOLTA_DO_MODE_DE_TERCEIRO = 31
VOLTA_DA_ACL_VELHA = 38
VOLTA_DO_EDGE_QUE_RENASCE = 45

STEAM = 4242
FILHO = 5151
OUTRO = 6161

IN_ATTRIB = 0x00000004
IN_Q_OVERFLOW = 0x00004000


# ---------------------------------------------------------------------------
# A mesa de mentira
# ---------------------------------------------------------------------------


@dataclass
class Mesa:
    raiz: Path
    dev: Path = field(init=False)
    dev_input: Path = field(init=False)
    sys_hidraw: Path = field(init=False)
    sys_input: Path = field(init=False)
    bluetooth: Path = field(init=False)

    def __post_init__(self) -> None:
        self.dev = self.raiz / "dev"
        self.dev_input = self.dev / "input"
        self.sys_hidraw = self.raiz / "sys" / "class" / "hidraw"
        self.sys_input = self.raiz / "sys" / "class" / "input"
        self.bluetooth = self.raiz / "sys" / "class" / "bluetooth"

    @staticmethod
    def _controle(jogador: str) -> tuple[str, str, str, str, str]:
        return next(c for c in CONTROLES if c[0] == jogador)

    def no(self, jogador: str) -> Path:
        return self.dev / self._controle(jogador)[1]

    def entradas(self, jogador: str) -> list[Path]:
        """Os nós de entrada no alcance do broker, na ordem gamepad, js, movimento, touchpad."""
        _, base, transporte, _, _ = self._controle(jogador)
        n = base.removeprefix("hidraw")
        nomes = [f"event{n}0", f"js{n}0", f"event{n}1", f"event{n}2"]
        if transporte == "cabo":
            nomes.append(f"event{n}3")  # a tomada do fone
        return [self.dev_input / nome for nome in nomes]

    def js_do_movimento(self, jogador: str) -> Path:
        return self.dev_input / f"js{self._controle(jogador)[1].removeprefix('hidraw')}1"

    def do_controle(self, jogador: str) -> list[Path]:
        return [self.no(jogador), *self.entradas(jogador)]

    def todos(self) -> list[Path]:
        return [p for j in JOGADORES for p in self.do_controle(j)]

    @property
    def vpad(self) -> Path:
        return self.dev / "hidraw4"


def _chave(mesa: Mesa, caminho: Path) -> str:
    """O nome como o `inotify` o entrega: `hidraw3` em `dev/`, `input/event30` em `dev/input/`."""
    return caminho.name if caminho.parent == mesa.dev else f"input/{caminho.name}"


def _abrir_para_ela(caminho: Path) -> None:
    """Uma regra que reabre (o `uaccess` do logind): `0660` + a ACL dela."""
    caminho.chmod(0o660)
    os.setxattr(caminho, ACL, encode_access_acl(UID))


def _nascer(mesa: Mesa, jogador: str, *, aberto: bool) -> None:
    """Cria (ou recria, com inode novo) os nós de `/dev` de um controle."""
    for caminho in [*mesa.do_controle(jogador), mesa.js_do_movimento(jogador)]:
        if caminho.exists():
            caminho.chmod(0o600)
            caminho.unlink()
        caminho.write_text("", encoding="ascii")
        caminho.chmod(0o600)  # a regra da cura: o físico nasce fechado
    mesa.js_do_movimento(jogador).chmod(0o000)  # a regra 80, para todos
    if aberto:
        for caminho in mesa.do_controle(jogador):
            _abrir_para_ela(caminho)


def _montar(raiz: Path, *, aberta: bool) -> Mesa:
    """Os quatro DualSense e o vpad. `aberta`: os 22 nós nascem com a ACL dela."""
    mesa = Mesa(raiz)
    for pasta in (mesa.dev_input, mesa.sys_hidraw, mesa.sys_input):
        pasta.mkdir(parents=True, exist_ok=True)
    (mesa.bluetooth / "hci0").mkdir(parents=True)
    (mesa.bluetooth / "hci0" / "address").write_text(MAC_DO_ADAPTADOR + "\n", encoding="ascii")
    for jogador, base, transporte, hid, mac in CONTROLES:
        n = base.removeprefix("hidraw")
        if transporte == "radio":
            topo = raiz / "sys" / "devices" / "virtual" / "misc" / "uhid"
            extra = f"HID_PHYS={MAC_DO_ADAPTADOR}\nHID_UNIQ={mac}\n"
        else:
            topo = raiz / "sys" / "devices" / "pci0000:00" / "usb1" / f"1-{n}" / f"1-{n}:1.3"
            extra = ""
        hid_dir = topo / hid
        hid_dir.mkdir(parents=True)
        bus, vendor, produto = hid[:4], hid[5:9], hid[10:14]
        (hid_dir / "uevent").write_text(
            f"DRIVER=playstation\nHID_ID={bus}:0000{vendor}:0000{produto}\nHID_NAME=x\n{extra}",
            encoding="ascii",
        )
        (mesa.sys_hidraw / base).mkdir()
        (mesa.sys_hidraw / base / "dev").write_text("0:0\n", encoding="ascii")
        (mesa.sys_hidraw / base / "device").symlink_to(hid_dir)
        nome = "DualSense Edge Wireless Controller" if produto == "0DF2" else (
            "DualSense Wireless Controller"
        )
        inputs = [
            (nome, (f"event{n}0", f"js{n}0")),
            (f"{nome} Motion Sensors", (f"event{n}1", f"js{n}1")),
            (f"{nome} Touchpad", (f"event{n}2",)),
        ]
        if transporte == "cabo":
            inputs.append((f"{nome} Headset Jack", (f"event{n}3",)))
        for i, (nome_do_input, filhos) in enumerate(inputs):
            d = hid_dir / "input" / f"input{n}{i}"
            d.mkdir(parents=True)
            (d / "name").write_text(nome_do_input + "\n", encoding="utf-8")
            for filho in filhos:
                (d / filho).mkdir()
                (d / filho / "dev").write_text("0:0\n", encoding="ascii")
                (mesa.sys_input / filho).symlink_to(d / filho)
        _nascer(mesa, jogador, aberto=aberta)
    # O NOSSO vpad, que o validador recusa: USB sob o uhid.
    vpad = raiz / "sys" / "devices" / "virtual" / "misc" / "uhid" / "0003:054C:0DF2.0004"
    vpad.mkdir(parents=True)
    (vpad / "uevent").write_text("HID_ID=0003:0000054C:00000DF2\nHID_NAME=x\n", encoding="ascii")
    (mesa.sys_hidraw / "hidraw4").mkdir()
    (mesa.sys_hidraw / "hidraw4" / "dev").write_text("0:0\n", encoding="ascii")
    (mesa.sys_hidraw / "hidraw4" / "device").symlink_to(vpad)
    mesa.vpad.write_text("", encoding="ascii")
    _abrir_para_ela(mesa.vpad)
    return mesa


class _StatQueAceitaArquivo(ModuleType):
    """O módulo `stat` com UMA troca: o `S_ISCHR` aceita arquivo comum.

    Só o `hidraw_broker` o recebe, e só enquanto o teste vive. O `S_IMODE`
    que a pergunta da cura usa é o do stdlib.
    """

    def __init__(self) -> None:
        super().__init__("stat")

    def __getattr__(self, nome: str) -> Any:
        return getattr(stat, nome)

    @staticmethod
    def S_ISCHR(modo: int) -> bool:  # noqa: N802 - espelha o nome do stdlib
        return stat.S_ISCHR(modo) or stat.S_ISREG(modo)


class _OpsDeArquivo(FsAclOps):
    """O `FsAclOps` de produção; o «é char device?» das entradas aceita arquivo."""

    _e_char_device = staticmethod(stat.S_ISREG)


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sonda = tmp_path / "sonda-de-acl"
    sonda.write_text("", encoding="ascii")
    try:
        os.setxattr(sonda, ACL, encode_access_acl(UID))
    except OSError as exc:  # pragma: no cover - depende do fs do CI
        pytest.skip(f"o fs de teste não guarda ACL POSIX: {exc}")
    finally:
        sonda.unlink()
    monkeypatch.setattr(hb, "stat_mod", _StatQueAceitaArquivo())
    return tmp_path


def _estado(mesa: Mesa, diario: list[tuple[str, dict[str, Any]]]) -> BrokerState:
    """O `BrokerState` de produção, com o validador e o `FsAclOps` de produção."""
    return BrokerState(
        allowed_uid=UID,
        ops=_OpsDeArquivo(
            sys_class_hidraw=str(mesa.sys_hidraw),
            dev_input_root=str(mesa.dev_input),
            sys_class_input=str(mesa.sys_input),
            sys_class_bluetooth=str(mesa.bluetooth),
        ),
        dev_root=str(mesa.dev),
        sys_class_hidraw=str(mesa.sys_hidraw),
        sys_class_bluetooth=str(mesa.bluetooth),
        dev_input_root=str(mesa.dev_input),
        sys_class_input=str(mesa.sys_input),
        log=lambda evento, **campos: diario.append((evento, campos)),
        sleep_fn=lambda _s: None,
        no_nasce_fechado=True,
    )


def _pede(st: BrokerState, payload: dict[str, Any]) -> dict[str, Any]:
    """Um pedido do daemon (a conexão 7), pelo `handle_line` de produção."""
    resposta, fd = st.handle_line(7, UID, json.dumps(payload).encode())
    if fd is not None:
        os.close(fd)
    return dict(resposta)


def _volta(st: BrokerState, mesa: Mesa) -> list[object]:
    """Uma volta do rehide: um `hide` por físico, na ordem do `rehide_physical_hidraw`."""
    return [
        _pede(st, {"cmd": "hide", "node": str(no)}).get("state")
        for no in sorted(str(mesa.no(j)) for j in JOGADORES)
    ]


def _fechado(caminho: Path) -> bool:
    """O alvo de fechar: `0600` e ACL nenhuma."""
    if stat.S_IMODE(caminho.stat().st_mode) != 0o600:
        return False
    try:
        os.getxattr(caminho, ACL)
    except OSError:
        return True
    return False


def _aberto_para_ela(caminho: Path) -> bool:
    """O alvo de abrir: `0660` e a ACL canônica dela, byte a byte."""
    try:
        blob = os.getxattr(caminho, ACL)
    except OSError:
        return False
    return stat.S_IMODE(caminho.stat().st_mode) == 0o660 and blob == encode_access_acl(UID)


def _ctimes(caminhos: list[Path]) -> dict[str, int]:
    return {str(c): c.stat().st_ctime_ns for c in caminhos}


class _Inotify:
    """O instrumento da medição: `IN_ATTRIB` nos diretórios da mesa, por nome."""

    def __init__(self, mesa: Mesa) -> None:
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        self._fd = int(libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC))
        if self._fd < 0:  # pragma: no cover - kernel sem inotify
            raise OSError(ctypes.get_errno(), "inotify_init1")
        self._prefixo: dict[int, str] = {}
        for pasta, prefixo in ((mesa.dev, ""), (mesa.dev_input, "input/")):
            wd = int(libc.inotify_add_watch(self._fd, os.fsencode(pasta), IN_ATTRIB))
            if wd < 0:  # pragma: no cover
                raise OSError(ctypes.get_errno(), f"inotify_add_watch {pasta}")
            self._prefixo[wd] = prefixo

    def drenar(self) -> Counter[str]:
        """Os `IN_ATTRIB` desde a última drenagem, por nó."""
        conta: Counter[str] = Counter()
        while True:
            try:
                buf = os.read(self._fd, 65536)
            except BlockingIOError:
                return conta
            i = 0
            while i < len(buf):
                wd, mascara, _cookie, tamanho = struct.unpack_from("iIII", buf, i)
                nome = buf[i + 16 : i + 16 + tamanho].rstrip(b"\0").decode()
                i += 16 + tamanho
                assert not mascara & IN_Q_OVERFLOW, "a fila do inotify transbordou"
                if mascara & IN_ATTRIB:
                    conta[self._prefixo[wd] + nome] += 1

    def fechar(self) -> None:
        os.close(self._fd)


@pytest.fixture
def abrir_inotify() -> Iterator[Callable[[Mesa], _Inotify]]:
    abertos: list[_Inotify] = []

    def abrir(mesa: Mesa) -> _Inotify:
        vigia = _Inotify(mesa)
        abertos.append(vigia)
        return vigia

    yield abrir
    for vigia in abertos:
        vigia.fechar()


def _resumo(por_volta: list[Counter[str]]) -> str:
    total: Counter[str] = Counter()
    for conta in por_volta:
        total.update(conta)
    voltas = sum(1 for conta in por_volta if conta)
    return f"{sum(total.values())} IN_ATTRIB em {voltas} de {len(por_volta)} voltas: {dict(total)}"


# ---------------------------------------------------------------------------
# As mudanças do meio da R2 (e da R4): cada uma é uma forma do mundo real
# ---------------------------------------------------------------------------


def _a_regra_que_reabre(mesa: Mesa) -> set[str]:
    """O hidraw e o event do gamepad do P3 voltam a `0660` com a ACL dela."""
    alvos = [mesa.no("P3"), mesa.entradas("P3")[0]]
    for caminho in alvos:
        _abrir_para_ela(caminho)
    return {_chave(mesa, c) for c in alvos}


def _o_mode_de_terceiro(mesa: Mesa) -> set[str]:
    """Uma regra de terceiro com `MODE="0666"`: o js do P2 abre para todos, sem ACL."""
    js = mesa.entradas("P2")[1]
    js.chmod(0o666)
    return {_chave(mesa, js)}


def _a_acl_velha(mesa: Mesa) -> set[str]:
    """Um event do P1 fica `0600` com uma ACL velha (a máscara `---`)."""
    movimento = mesa.entradas("P1")[2]
    os.setxattr(movimento, ACL, encode_access_acl(UID))
    movimento.chmod(0o600)
    return {_chave(mesa, movimento)}


def _o_edge_que_renasce(mesa: Mesa) -> set[str]:
    """O Edge renasce com o MESMO `hidrawN`: arquivos novos, inode novo, abertos."""
    _nascer(mesa, "P4", aberto=True)
    return {_chave(mesa, c) for c in mesa.do_controle("P4")}


MUDANCAS: dict[int, Callable[[Mesa], set[str]]] = {
    VOLTA_DA_REGRA_QUE_REABRE: _a_regra_que_reabre,
    VOLTA_DO_MODE_DE_TERCEIRO: _o_mode_de_terceiro,
    VOLTA_DA_ACL_VELHA: _a_acl_velha,
    VOLTA_DO_EDGE_QUE_RENASCE: _o_edge_que_renasce,
}
#: As mudanças que mexem num HIDRAW — as únicas cuja firma a vigia lê.
MUDANCAS_NO_HIDRAW = {VOLTA_DA_REGRA_QUE_REABRE, VOLTA_DO_EDGE_QUE_RENASCE}


# ---------------------------------------------------------------------------
# R0 — a mesa alcança o kernel
# ---------------------------------------------------------------------------


class TestR0AMesaAlcancaOKernel:
    def test_a_primeira_volta_escreve_nos_22_nos_e_fecha_todos(
        self, raiz: Path, abrir_inotify: Callable[[Mesa], _Inotify]
    ) -> None:
        """Os nós nascem abertos para ela (uma regra que reabre), e a primeira
        volta é uma transição de verdade: cada nó recebe ao menos um
        `IN_ATTRIB` e termina `0600` sem ACL.

        Sem este irmão, uma mesa cujo instrumento não visse nada deixaria a R1
        verde sobre nada. A MORDIDA: desligue o `inotify` (o `add_watch` com
        máscara 0) e esta régua reprova.
        """
        mesa = _montar(raiz, aberta=True)
        diario: list[tuple[str, dict[str, Any]]] = []
        st = _estado(mesa, diario)
        vigia = abrir_inotify(mesa)
        vigia.drenar()
        js_do_movimento = {j: mesa.js_do_movimento(j).stat().st_ctime_ns for j in JOGADORES}

        assert _volta(st, mesa) == ["hidden"] * 4
        eventos = vigia.drenar()

        assert len(mesa.todos()) == 22
        assert set(eventos) == {_chave(mesa, c) for c in mesa.todos()}, eventos
        assert all(_fechado(c) for c in mesa.todos())
        for jogador in JOGADORES:
            js = mesa.js_do_movimento(jogador)
            assert stat.S_IMODE(js.stat().st_mode) == 0, "o js do movimento é da regra 80"
            assert js.stat().st_ctime_ns == js_do_movimento[jogador]

    def test_o_vpad_e_recusado_e_ninguem_mexe_nele(
        self, raiz: Path, abrir_inotify: Callable[[Mesa], _Inotify]
    ) -> None:
        mesa = _montar(raiz, aberta=True)
        st = _estado(mesa, [])
        vigia = abrir_inotify(mesa)
        vigia.drenar()

        resposta = _pede(st, {"cmd": "hide", "node": str(mesa.vpad)})

        assert resposta["error"] == "reject_not_physical_dualsense"
        assert vigia.drenar() == Counter()
        assert _aberto_para_ela(mesa.vpad)


# ---------------------------------------------------------------------------
# R1 — no tempo: sessenta voltas com os nós parados não escrevem nada
# ---------------------------------------------------------------------------


class TestR1NoTempo:
    def test_sessenta_voltas_de_rehide_com_os_nos_parados(
        self, raiz: Path, abrir_inotify: Callable[[Mesa], _Inotify]
    ) -> None:
        """30 min de mesa. A cada volta, e não só no fim: zero `IN_ATTRIB`,
        `ctime` parado nos 22 nós, `hidden` nas quatro respostas e nenhuma
        linha no diário — o rehide segue mudo, como já era.

        AS MORDIDAS, as duas medidas em 25/09:
          - sem a pergunta no `hide`: 1 `IN_ATTRIB` por hidraw por volta
            (240 em 60 voltas);
          - sem a pergunta no `fechar_entradas`: 1 por nó de entrada por volta
            (1.080 em 60 voltas).
        """
        mesa = _montar(raiz, aberta=True)
        diario: list[tuple[str, dict[str, Any]]] = []
        st = _estado(mesa, diario)
        vigia = abrir_inotify(mesa)
        _volta(st, mesa)  # a R0: a transição de verdade
        vigia.drenar()
        ctimes = _ctimes(mesa.todos())
        linhas = len(diario)

        por_volta: list[Counter[str]] = []
        ctime_andou: dict[int, list[str]] = {}
        for volta in range(1, 61):
            assert _volta(st, mesa) == ["hidden"] * 4, volta
            por_volta.append(vigia.drenar())
            agora = _ctimes(mesa.todos())
            andou = sorted(no for no, ctime in agora.items() if ctime != ctimes[no])
            if andou:
                ctime_andou[volta] = andou
            ctimes = agora
            assert diario[linhas:] == [], volta

        assert all(not conta for conta in por_volta), _resumo(por_volta)
        assert ctime_andou == {}, f"o ctime andou em {len(ctime_andou)} de 60 voltas"
        assert all(_fechado(c) for c in mesa.todos())


# ---------------------------------------------------------------------------
# R2 — o que já funcionava: a reconvergência
# ---------------------------------------------------------------------------


class TestR2AReconvergencia:
    def test_so_o_no_que_mudou_e_escrito_e_volta_fechado(
        self, raiz: Path, abrir_inotify: Callable[[Mesa], _Inotify]
    ) -> None:
        """No meio das sessenta voltas, quatro formas do mundo real mexem num
        nó (`MUDANCAS`). Na volta seguinte a cada uma, SÓ esses nós recebem
        `IN_ATTRIB`, e todos terminam `0600` sem ACL; na volta depois dela,
        zero de novo. É o rehide sendo o que sempre foi: a reconvergência
        contra o que não avisa o broker.

        AS MORDIDAS, uma por forma errada da pergunta:
          - perguntar «ela consegue abrir?» (`is_exposed_to`) deixa o `0666`
            do js do P2 aberto;
          - lembrar em memória (o nó já fechado por caminho) deixa o Edge
            renascido aberto;
          - olhar só o modo deixa a ACL velha do event do P1.
        """
        mesa = _montar(raiz, aberta=True)
        st = _estado(mesa, [])
        vigia = abrir_inotify(mesa)
        _volta(st, mesa)
        vigia.drenar()

        escritos: dict[int, Counter[str]] = {}
        esperados: dict[int, set[str]] = {}
        #: nó -> a primeira volta depois da qual ele ficou aberto.
        ficou_aberto: dict[str, int] = {}
        for volta in range(1, 61):
            mudar = MUDANCAS.get(volta)
            if mudar is not None:
                esperados[volta] = mudar(mesa)
                vigia.drenar()  # o que a mudança disparou não é do broker
            assert _volta(st, mesa) == ["hidden"] * 4, volta
            escritos[volta] = vigia.drenar()
            for caminho in mesa.todos():
                if not _fechado(caminho):
                    ficou_aberto.setdefault(_chave(mesa, caminho), volta)

        assert ficou_aberto == {}, ficou_aberto
        for volta in range(1, 61):
            assert set(escritos[volta]) == esperados.get(volta, set()), (
                volta,
                dict(escritos[volta]),
            )
        for jogador in JOGADORES:
            assert stat.S_IMODE(mesa.js_do_movimento(jogador).stat().st_mode) == 0


# ---------------------------------------------------------------------------
# R3 — o lado de abrir (o Modo Nativo)
# ---------------------------------------------------------------------------


def _acl_com_dois(uid: int, outro: int) -> bytes:
    """A ACL dela e a de um segundo uid, no formato do kernel (entradas por tag e id)."""
    indefinido = 0xFFFFFFFF
    entradas = (
        (0x01, 0x06, indefinido),
        (0x02, 0x06, min(uid, outro)),
        (0x02, 0x06, max(uid, outro)),
        (0x04, 0x06, indefinido),
        (0x10, 0x06, indefinido),
        (0x20, 0x00, indefinido),
    )
    return struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *e) for e in entradas)


class TestR3OLadoDeAbrir:
    def test_o_expose_repetido_nao_escreve_e_o_que_mudou_e_reescrito(
        self, raiz: Path, abrir_inotify: Callable[[Mesa], _Inotify]
    ) -> None:
        """O Modo Nativo pede `expose` com `"entradas": true`. O primeiro pedido
        escreve; os trinta iguais seguintes, nada. O nó que renasce `0600` é
        escrito no pedido seguinte, e o nó com a ACL dela E a de um segundo
        uid volta ao blob canônico — o alvo é o blob, não «ela consegue
        abrir?».

        AS MORDIDAS:
          - sem a pergunta no `restore` e no `abrir_entradas`, cada pedido
            gera `IN_ATTRIB` nos cinco nós do P1;
          - perguntar `is_exposed_to(uid)` deixa o segundo uid na ACL.
        """
        mesa = _montar(raiz, aberta=False)
        st = _estado(mesa, [])
        vigia = abrir_inotify(mesa)
        vigia.drenar()
        p1 = {_chave(mesa, c) for c in mesa.do_controle("P1")}
        pedido = {"cmd": "expose", "node": str(mesa.no("P1")), "entradas": True}

        assert _pede(st, pedido)["state"] == "exposed"
        assert set(vigia.drenar()) == p1
        assert all(_aberto_para_ela(c) for c in mesa.do_controle("P1"))

        repetidos = []
        for _ in range(30):
            assert _pede(st, pedido)["state"] == "exposed"
            repetidos.append(vigia.drenar())
        assert all(not conta for conta in repetidos), _resumo(repetidos)

        _nascer(mesa, "P1", aberto=False)  # o replug: o nó renasce fechado
        vigia.drenar()
        assert _pede(st, pedido)["state"] == "exposed"
        assert set(vigia.drenar()) == p1
        assert all(_aberto_para_ela(c) for c in mesa.do_controle("P1"))

        com_dois = [mesa.no("P1"), mesa.entradas("P1")[0]]
        try:
            for caminho in com_dois:
                os.setxattr(caminho, ACL, _acl_com_dois(UID, UID + 1))
        except OSError as exc:  # pragma: no cover - uid sem mapeamento no namespace
            pytest.skip(f"o fs não aceita a ACL com um segundo uid: {exc}")
        assert all(UID + 1 in decode_acl_user_uids(os.getxattr(c, ACL)) for c in com_dois)
        vigia.drenar()
        assert _pede(st, pedido)["state"] == "exposed"
        assert set(vigia.drenar()) == {_chave(mesa, c) for c in com_dois}
        assert all(_aberto_para_ela(c) for c in mesa.do_controle("P1"))

        assert _pede(st, pedido)["state"] == "exposed"
        assert vigia.drenar() == Counter()
        assert all(_fechado(c) for j in ("P2", "P3", "P4") for c in mesa.do_controle(j))


# ---------------------------------------------------------------------------
# A vigia do sequestro sobre a mesa: firma REAL, /proc e relógio de mentira
# ---------------------------------------------------------------------------


class _Proc:
    """O `/proc` de mentira: quem segura cada nó e quem está vivo. A sonda conta.

    Processo morto não aparece na varredura, como no `/proc` de verdade.
    """

    def __init__(self) -> None:
        self.donos: dict[str, list[int]] = {}
        self.vivos: set[int] = set()
        self.varreduras = 0

    def sonda(self, nos: Any) -> dict[str, list[int]]:
        self.varreduras += 1
        alvos = set(nos)
        return {
            n: [p for p in pids if p in self.vivos]
            for n, pids in self.donos.items()
            if n in alvos and any(p in self.vivos for p in pids)
        }

    def vivo(self, pid: int) -> bool:
        return pid in self.vivos

    def segurar(self, no: str, pid: int) -> None:
        self.donos.setdefault(no, []).append(pid)
        self.vivos.add(pid)

    def morrer(self, pid: int) -> None:
        self.vivos.discard(pid)
        for pids in self.donos.values():
            if pid in pids:
                pids.remove(pid)


def _ela_abre(no: str) -> bool:
    """O `access(2)` de um processo dela sobre o nó, que na máquina é de root.

    Na mesa o arquivo é do usuário do teste, e o `access(2)` de verdade diria
    «abre» até num `0600`. Aqui a pergunta é a do kernel para quem NÃO é dono:
    os bits de outros, ou a entrada dela na ACL com a máscara (os bits de
    grupo) deixando ler e escrever.
    """
    try:
        modo = stat.S_IMODE(os.stat(no).st_mode)
    except OSError:
        return False
    if modo & 0o006 == 0o006:
        return True
    try:
        uids = decode_acl_user_uids(os.getxattr(no, ACL))
    except OSError:
        return False
    return UID in uids and modo & 0o060 == 0o060


def _espera_o_relogio_do_fs(sonda: Path) -> None:
    """Espera o relógio do fs passar da última escrita (teto de 50 ms).

    Dois `chmod` no mesmo tique do relógio do fs dão o mesmo `ctime`, e a
    mordida da R4 contaria de menos: o rehide que escreve não andaria a firma.
    """
    sonda.chmod(0o600)
    antes = sonda.stat().st_ctime_ns
    fim = time.monotonic() + 0.05
    while time.monotonic() < fim:
        sonda.chmod(0o600)
        if sonda.stat().st_ctime_ns != antes:
            return


class _Bancada:
    """A `VigiaDoSequestro` de produção sobre os hidraw da mesa, no tempo.

    Uma fatia de 2 s (`RECONNECT_HOTPLUG_POLL_INTERVAL_SEC`), que encolhe para
    `PASSO_DA_VIGIA_S` com a vigia alerta, como no `_wait_online_or_hotplug`;
    e o rehide do `BrokerState` a cada 30 s, seguido de um passo da vigia na
    mesma hora, como no `reconnect_loop`.
    """

    def __init__(self, raiz: Path, mesa: Mesa, st: BrokerState, proc: _Proc) -> None:
        self.mesa = mesa
        self.st = st
        self.proc = proc
        self.vigia = ec.VigiaDoSequestro(
            sonda=proc.sonda, alcancavel=_ela_abre, vivo=proc.vivo, firma=ec.firma_do_no
        )
        self.hidraws = sorted(str(mesa.no(j)) for j in JOGADORES)
        self.relogio = raiz / "relogio-do-fs"
        self.relogio.write_text("", encoding="ascii")
        self.t = 0.0
        self.rehides = 0
        self._proximo_rehide = 30.0
        self.antes_do_rehide: dict[int, Callable[[Mesa], object]] = {}
        #: (t, passo) de cada passo dado.
        self.passos: list[tuple[float, ec.PassoDaVigia]] = []

    def passo(self) -> ec.PassoDaVigia:
        sondar = self.vigia.quer_sondar(self.hidraws, self.t)
        passo = self.vigia.passo(self.hidraws, self.t, sondar=sondar)
        self.vigia.reafirmado(passo.a_reafirmar, self.t)
        self.passos.append((self.t, passo))
        return passo

    def rehide(self) -> None:
        self.rehides += 1
        _espera_o_relogio_do_fs(self.relogio)
        mudar = self.antes_do_rehide.get(self.rehides)
        if mudar is not None:
            mudar(self.mesa)
        assert _volta(self.st, self.mesa) == ["hidden"] * 4, self.rehides

    def fatia(self) -> ec.PassoDaVigia:
        largura = ec.PASSO_DA_VIGIA_S if self.vigia.vigilante else 2.0
        self.t = round(self.t + largura, 6)
        if self.t >= self._proximo_rehide:
            self.rehide()
            self._proximo_rehide += 30.0
        return self.passo()

    def andar_ate(
        self, fim: float, *, parar: Callable[[ec.PassoDaVigia], bool] | None = None
    ) -> float | None:
        """Fatias até `fim`; com `parar`, devolve o `t` do primeiro passo que casa."""
        while self.t < fim:
            passo = self.fatia()
            if parar is not None and parar(passo):
                return self.t
        return None


def _bancada(raiz: Path) -> _Bancada:
    """A mesa FECHADA (depois da R0), o broker, e a vigia com a primeira vista dada."""
    mesa = _montar(raiz, aberta=True)
    st = _estado(mesa, [])
    _volta(st, mesa)
    bancada = _Bancada(raiz, mesa, st, _Proc())
    bancada.passo()
    return bancada


# ---------------------------------------------------------------------------
# R4 — a vigia volta ao desenho dela
# ---------------------------------------------------------------------------


class TestR4AVigiaVoltaAoDesenhoDela:
    def test_com_os_nos_parados_uma_varredura_so(self, raiz: Path) -> None:
        """«Nó fechado, firma parada e ninguém segurando: nunca» — o desenho da
        vigia. Um passo a cada 2 s por 30 min e o rehide a cada 30 s: uma
        varredura, a da primeira vista.

        A MORDIDA: sem a pergunta no `hide`, o `chmod` de cada rehide anda o
        `ctime` e a vigia varre o `/proc` uma vez por volta — 61 varreduras,
        60 delas sobre nada.
        """
        bancada = _bancada(raiz)
        ctimes = _ctimes([bancada.mesa.no(j) for j in JOGADORES])

        bancada.andar_ate(1800.0)

        assert bancada.rehides == 60
        assert bancada.proc.varreduras == 1, bancada.proc.varreduras
        assert _ctimes([bancada.mesa.no(j) for j in JOGADORES]) == ctimes
        assert not any(p.a_reafirmar for _t, p in bancada.passos)

    def test_cada_mudanca_de_verdade_no_hidraw_custa_uma_varredura(self, raiz: Path) -> None:
        """As mudanças da R2, no meio dos 30 min. As duas que mexem num hidraw
        (a regra que reabre o do P3, e o Edge que renasce) custam uma
        varredura cada; as dos nós de entrada, nenhuma — a vigia lê só a firma
        do hidraw. É o fd que entrou pela janela sendo visto depois de ela
        fechar, e é o caminho das três detecções de 25/09."""
        bancada = _bancada(raiz)
        bancada.antes_do_rehide = {volta: mudar for volta, mudar in MUDANCAS.items()}

        bancada.andar_ate(1800.0)

        assert bancada.rehides == 60
        assert bancada.proc.varreduras == 1 + len(MUDANCAS_NO_HIDRAW), bancada.proc.varreduras
        assert all(_fechado(c) for c in bancada.mesa.todos())
