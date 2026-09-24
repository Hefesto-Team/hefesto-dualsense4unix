"""HIDE-SO-O-HIDRAW-02 — os quatro nós de entrada do físico somem como o hidraw.

A palavra dela, 23/09/2026, escolhida entre as opções: **«Esconder tudo»**. Os
nós de entrada do DualSense FÍSICO (o gamepad, o touchpad, os sensores de
movimento e a tomada do fone em `/dev/input/eventN`, e o joystick legado em
`/dev/input/jsN`) somem para todos menos para o Hefesto, e só o Modo Nativo os
devolve.

O que o doctor acusava antes, com o hidraw já fechado::

    [WARN] o hide cobre SÓ o hidraw: 0 de 1 controle(s) escondido(s) do jogo —
    o FÍSICO segue alcançável em 4 nó(s) de entrada (event27 event28 event29 js1)

Esta régua é de UNIDADE, como a da O-NO-NASCE-FECHADO-01: nada aqui toca
/dev, /sys, o udev vivo, o broker vivo nem o daemon. A regra udev é lida do
asset como TEXTO e rodada num udev de bolso; o sysfs é uma árvore de mentira em
`tmp_path`, com arquivos comuns no lugar dos char devices (a suíte não cria
char device sem root). Nos testes do `FsAclOps`, a ÚNICA coisa trocada é o
«é char device?» (`_e_char_device`) e o ioctl do EVIOCGID (`_ler_input_id`):
toda a decisão — o rdev contra o sysfs, a identidade do pai HID, as marcas do
vpad, o chmod e a ACL — é a de produção.

As cinco pontas, e cada uma tem mordida escrita no teste que a cobra:
  1. a regra 72 fecha os nós de entrada do físico, e só com o broker de pé;
  2. o broker acha os nós de entrada pelo pai HID e os fecha/abre de verdade;
  3. o broker serve o fd do `/dev/input/eventN` do físico, e recusa o do vpad;
  4. os nós de entrada seguem a lease: fechados com o hide, abertos SÓ pelo
     pedido do Modo Nativo (`expose` com `"entradas": true`);
  5. o reinício pedido não abre nada — o achado do install de 24/09.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import (
    BrokerState,
    FsAclOps,
    StaleNodeError,
    decode_acl_user_uids,
    encode_access_acl,
    fechar_todo_fisico,
    reinicio_sem_abrir_pedido,
    restore_all_physical,
    validate_physical_input_node,
)

RAIZ = Path(__file__).resolve().parents[2]
REGRA_72 = RAIZ / "assets" / "72-hefesto-touchpad-motion-uaccess.rules"
TRANSFORMA = RAIZ / "scripts" / "regra_do_no_aberta.sh"
SOCKET_DO_BROKER = "/run/hefesto-hidraw-broker/broker.sock"

UID = os.getuid()
#: Faixas sintéticas da casa para fixture: nunca endereço real mascarado.
MAC_DO_CONTROLE = "e8:47:3a:00:00:07"
MAC_DO_ADAPTADOR = "aa:bb:cc:00:00:01"


# ---------------------------------------------------------------------------
# 1. A REGRA 72 — o udev de bolso, agora para nós de ENTRADA
# ---------------------------------------------------------------------------


def _linhas_de_codigo(caminho: Path) -> list[str]:
    return [
        ln.strip()
        for ln in caminho.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


class _NoDeEntrada:
    """Um nó de `/dev/input` como o udev o vê, já com o que o sistema fez antes.

    `pais` é a corrente do nó para cima; `KERNELS`/`ATTRS` de uma linha casam
    no MESMO elo, que é a regra do udev. O estado inicial é o que as regras
    do sistema deixam antes do 72: o `70-uaccess.rules` pôs `uaccess` no
    gamepad (ID_INPUT_JOYSTICK), o `50-udev-default` pôs 0660 (event) ou 0664
    (js) com grupo `input`.
    """

    def __init__(self, devpath: str, pais: list[tuple[str, dict[str, str]]]) -> None:
        self.devpath = devpath
        self.kernel = devpath.rsplit("/", 1)[-1]
        self.pais = [(self.kernel, {}), *pais]
        self.mode = "0664" if self.kernel.startswith("js") else "0660"
        self.owner = "root"
        self.group = "input"
        nome = pais[0][1].get("name", "")
        eh_gamepad = not nome.endswith(("Motion Sensors", "Touchpad", "Headset Jack"))
        self.tags: set[str] = {"uaccess"} if eh_gamepad else set()


def _casa(padrao: str, valor: str) -> bool:
    import fnmatch

    return any(fnmatch.fnmatchcase(valor, p) for p in padrao.split("|"))


def _aplicar_a_72(no: _NoDeEntrada, *, existe: set[str]) -> _NoDeEntrada:
    """Roda as linhas do asset, EM ORDEM, sobre um nó. `existe` responde o TEST."""
    termo = re.compile(r'(\w+(?:\{[^}]*\})?)\s*(==|!=|\+=|-=|=)\s*"([^"]*)"')
    for linha in _linhas_de_codigo(REGRA_72):
        termos = termo.findall(linha)
        casou = True
        de_pai: list[tuple[str, str]] = []
        for chave, op, valor in termos:
            if op not in ("==", "!="):
                continue
            if chave == "ACTION":
                ok = _casa(valor, "add")
            elif chave == "SUBSYSTEM":
                ok = valor == "input"
            elif chave == "KERNEL":
                ok = _casa(valor, no.kernel)
            elif chave == "DEVPATH":
                ok = _casa(valor, no.devpath)
            elif chave == "TEST":
                ok = valor in existe
            elif chave == "KERNELS" or chave.startswith("ATTRS{"):
                de_pai.append((chave, valor))
                continue
            else:
                ok = False
            if (op == "==") != ok:
                casou = False
        if casou and de_pai:
            casou = any(
                all(
                    _casa(valor, kernel)
                    if chave == "KERNELS"
                    else _casa(valor, attrs.get(chave[6:-1], "\0"))
                    for chave, valor in de_pai
                )
                for kernel, attrs in no.pais
            )
        if not casou:
            continue
        for chave, op, valor in termos:
            if chave == "MODE" and op == "=":
                no.mode = valor
            elif chave == "OWNER" and op == "=":
                no.owner = valor
            elif chave == "GROUP" and op == "=":
                no.group = valor
            elif chave == "TAG" and op == "+=":
                no.tags.add(valor)
            elif chave == "TAG" and op == "-=":
                no.tags.discard(valor)
    return no


_NOMES = {
    "gamepad": ("DualSense Wireless Controller", "event27"),
    "movimento": ("DualSense Wireless Controller Motion Sensors", "event28"),
    "touchpad": ("DualSense Wireless Controller Touchpad", "event29"),
    "fone": ("DualSense Wireless Controller Headset Jack", "event30"),
    "joystick": ("DualSense Wireless Controller", "js1"),
}


def _pelo_radio(qual: str, pid: str = "0CE6") -> _NoDeEntrada:
    nome, kernel = _NOMES[qual]
    hid = f"0005:054C:{pid}.0006"
    return _NoDeEntrada(
        f"/devices/virtual/misc/uhid/{hid}/input/input45/{kernel}",
        [
            ("input45", {"id/vendor": "054c", "id/product": pid.lower(), "name": nome,
                         "uniq": MAC_DO_CONTROLE}),
            (hid, {}),
            ("uhid", {}),
        ],
    )


def _pelo_cabo(qual: str, pid: str = "0CE6") -> _NoDeEntrada:
    nome, kernel = _NOMES[qual]
    hid = f"0003:054C:{pid}.0008"
    return _NoDeEntrada(
        f"/devices/pci0000:00/0000:00:14.0/usb1/1-4/1-4:1.3/{hid}/input/input46/{kernel}",
        [
            ("input46", {"id/vendor": "054c", "id/product": pid.lower(), "name": nome,
                         "uniq": MAC_DO_CONTROLE}),
            (hid, {}),
            ("1-4:1.3", {}),
            ("1-4", {"idVendor": "054c", "idProduct": pid.lower()}),
        ],
    )


def _do_vpad(qual: str) -> _NoDeEntrada:
    nome, kernel = _NOMES[qual]
    nome = nome.replace("Controller", "Controller (Hefesto P1)")
    hid = "0003:054C:0DF2.001C"
    return _NoDeEntrada(
        f"/devices/virtual/misc/uhid/{hid}/input/input128/{kernel}",
        [
            ("input128", {"id/vendor": "054c", "id/product": "0df2", "name": nome,
                          "uniq": "02:fe:00:00:00:01"}),
            (hid, {}),
            ("uhid", {}),
        ],
    )


_TODOS = ("gamepad", "movimento", "touchpad", "fone", "joystick")


class TestARegraFechaOsNosDeEntrada:
    @pytest.mark.parametrize("qual", _TODOS)
    @pytest.mark.parametrize(
        "montar",
        [
            pytest.param(lambda q: _pelo_radio(q), id="standard-radio"),
            pytest.param(lambda q: _pelo_cabo(q), id="standard-cabo"),
            pytest.param(lambda q: _pelo_radio(q, "0DF2"), id="edge-radio"),
            pytest.param(lambda q: _pelo_cabo(q, "0DF2"), id="edge-cabo"),
        ],
    )
    def test_o_fisico_nasce_0600_de_root_sem_uaccess(self, montar: Any, qual: str) -> None:
        """Os quatro nós, nos dois transportes, standard e Edge.

        A MORDIDA: suba as duas linhas de fechar para ANTES das de acesso e o
        touchpad e o movimento saem daqui com `uaccess` — a linha de acesso
        (`ATTRS{name}=="*Touchpad"`) os reabre depois de fechados.
        """
        no = _aplicar_a_72(montar(qual), existe={SOCKET_DO_BROKER})

        assert no.mode == "0600", (qual, no.mode)
        assert no.owner == "root"
        assert no.group == "root"
        assert "uaccess" not in no.tags, (qual, no.tags)

    @pytest.mark.parametrize("qual", _TODOS)
    def test_o_vpad_continua_aberto(self, qual: str) -> None:
        """O vpad é o controle que o Hefesto ENTREGA ao jogo.

        A MORDIDA: tire o `DEVPATH!=` da linha do cabo e o vpad fecha — ele é
        `0003:054C:0DF2` como o Edge físico pelo cabo.
        """
        no = _aplicar_a_72(_do_vpad(qual), existe={SOCKET_DO_BROKER})

        assert no.mode != "0600", (qual, no.mode)
        if qual in ("gamepad", "joystick", "movimento", "touchpad"):
            assert "uaccess" in no.tags, (qual, no.tags)

    @pytest.mark.parametrize("qual", _TODOS)
    def test_sem_o_broker_de_pe_nada_fecha(self, qual: str) -> None:
        """Sem broker, fechar é matar o gamepad inteiro: o daemon lê por aqui.

        É o que protege os pacotes de distro que não instalam o broker, e a
        máquina em que ele foi desinstalado. A MORDIDA: tire o `TEST==` e o
        físico sai fechado com o socket ausente.
        """
        antes = _pelo_radio(qual)
        tags_antes = set(antes.tags)
        no = _aplicar_a_72(antes, existe=set())

        assert no.mode != "0600", (qual, no.mode)
        assert tags_antes <= no.tags, (qual, no.tags)

    def test_as_linhas_de_fechar_vem_depois_das_de_acesso(self) -> None:
        linhas = _linhas_de_codigo(REGRA_72)
        ultima_de_acesso = max(i for i, ln in enumerate(linhas) if 'TAG+="uaccess"' in ln)
        primeira_de_fechar = min(i for i, ln in enumerate(linhas) if 'TAG-="uaccess"' in ln)
        assert ultima_de_acesso < primeira_de_fechar

    def test_a_variante_aberta_sai_do_mesmo_script_da_70(self, tmp_path: Path) -> None:
        """«Uma regra de udev, um dono»: o `--no-fechar-o-no` reabre as duas.

        A cura só é reversível sem editar asset se o `regra_do_no_aberta.sh`
        — o dono da transformação desde 20/09 — souber abrir também estas
        linhas. A MORDIDA: escreva as linhas de fechar sem o `GROUP="root"` e
        o `sed` dele não as alcança; a guarda 1 dele reprova e isto também.
        """
        destino = tmp_path / "72-aberta.rules"
        r = subprocess.run(
            ["bash", str(TRANSFORMA), str(REGRA_72), str(destino)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, r.stderr
        aberta = _linhas_de_codigo(destino)
        assert not any('TAG-="uaccess"' in ln for ln in aberta)
        do_fisico = [ln for ln in aberta if "054C:0CE6" in ln]
        assert len(do_fisico) == 2
        for ln in do_fisico:
            assert 'MODE="0660"' in ln and 'TAG+="uaccess"' in ln, ln


# ---------------------------------------------------------------------------
# 2. O SYSFS DE MENTIRA — um aparelho com os seus nós de entrada
# ---------------------------------------------------------------------------


@dataclass
class Mesa:
    raiz: Path
    sys_hidraw: Path
    sys_input: Path
    dev: Path
    dev_input: Path
    bluetooth: Path

    def ops(self) -> _OpsDeArquivo:
        return _OpsDeArquivo(
            sys_class_hidraw=str(self.sys_hidraw),
            dev_input_root=str(self.dev_input),
            sys_class_input=str(self.sys_input),
            sys_class_bluetooth=str(self.bluetooth),
        )


class _OpsDeArquivo(FsAclOps):
    """O `FsAclOps` de produção aceitando ARQUIVO COMUM no lugar do char device.

    Só isso muda. O arquivo comum tem `st_rdev == 0`, e o `dev` do sysfs de
    mentira diz `0:0` — o cruzamento do rdev continua sendo o de produção.
    """

    _e_char_device = staticmethod(stat.S_ISREG)
    input_id: tuple[int, int, int, int] = (0x0005, 0x054C, 0x0CE6, 0x8111)

    def _ler_input_id(self, fd: int) -> tuple[int, int, int, int]:
        return self.input_id


_INPUTS_DO_DUALSENSE = (
    ("input45", "DualSense Wireless Controller", ("event27", "js1")),
    ("input46", "DualSense Wireless Controller Motion Sensors", ("event28", "js2")),
    ("input47", "DualSense Wireless Controller Touchpad", ("event29",)),
    ("input48", "DualSense Wireless Controller Headset Jack", ("event30",)),
)


def _montar(
    tmp_path: Path,
    *,
    hid: str = "0005:054C:0CE6.0006",
    sob_uhid: bool = True,
    extra: str = f"HID_PHYS={MAC_DO_ADAPTADOR}\nHID_UNIQ={MAC_DO_CONTROLE}\n",
    base: str = "hidraw5",
    inputs: tuple[tuple[str, str, tuple[str, ...]], ...] = _INPUTS_DO_DUALSENSE,
) -> Mesa:
    mesa = Mesa(
        raiz=tmp_path,
        sys_hidraw=tmp_path / "sys" / "class" / "hidraw",
        sys_input=tmp_path / "sys" / "class" / "input",
        dev=tmp_path / "dev",
        dev_input=tmp_path / "dev" / "input",
        bluetooth=tmp_path / "sys" / "class" / "bluetooth-que-nao-existe",
    )
    for pasta in (mesa.sys_hidraw, mesa.sys_input, mesa.dev_input):
        pasta.mkdir(parents=True, exist_ok=True)
    topo = (
        tmp_path / "sys" / "devices" / "virtual" / "misc" / "uhid"
        if sob_uhid
        else tmp_path / "sys" / "devices" / "pci0000:00" / "usb1" / "1-4" / "1-4:1.3"
    )
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
    (mesa.dev / base).write_text("", encoding="ascii")
    for pasta_input, nome, filhos in inputs:
        d = hid_dir / "input" / pasta_input
        d.mkdir(parents=True)
        (d / "name").write_text(nome + "\n", encoding="utf-8")
        (d / "device").symlink_to(hid_dir)
        for filho in filhos:
            (d / filho).mkdir()
            (d / filho / "dev").write_text("0:0\n", encoding="ascii")
            (d / filho / "device").symlink_to(d)
            (mesa.sys_input / filho).symlink_to(d / filho)
            no = mesa.dev_input / filho
            no.write_text("", encoding="ascii")
            no.chmod(0o660)
    return mesa


def _modo(caminho: Path) -> int:
    return stat.S_IMODE(caminho.stat().st_mode)


def _acl_do(caminho: Path) -> set[int]:
    try:
        return decode_acl_user_uids(os.getxattr(caminho, "system.posix_acl_access"))
    except OSError:
        return set()


@pytest.fixture
def acl_funciona(tmp_path: Path) -> None:
    sonda = tmp_path / "sonda-de-acl"
    sonda.write_text("", encoding="ascii")
    try:
        os.setxattr(sonda, "system.posix_acl_access", encode_access_acl(UID))
    except OSError as exc:  # pragma: no cover - depende do fs do CI
        pytest.skip(f"o fs de teste não guarda ACL POSIX: {exc}")
    finally:
        sonda.unlink()


class TestOsNosDeEntradaDoAparelho:
    def test_acha_os_quatro_eventos_e_o_joystick_mas_nao_o_js_do_movimento(
        self, tmp_path: Path
    ) -> None:
        """A MORDIDA: tire o `continue` do `jsN` de movimento e o `js2` entra
        — o `restore` daria à sessão o joystick fantasma que a regra 80 fecha
        para todos."""
        mesa = _montar(tmp_path)
        nos = [no for no, _ in mesa.ops().entradas_do_no("hidraw5")]
        nomes = sorted(Path(no).name for no in nos)
        assert nomes == ["event27", "event28", "event29", "event30", "js1"]

    def test_pelo_cabo_tambem(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path, hid="0003:054C:0CE6.0008", sob_uhid=False, extra="")
        assert len(mesa.ops().entradas_do_no("hidraw5")) == 5

    def test_o_vpad_nao_tem_nos_de_entrada_para_o_broker(self, tmp_path: Path) -> None:
        """D1: USB sob `/misc/uhid/` é o vpad. Fechar os nós dele é tirar o
        controle do jogo — o mesmo cinto que recusa o hidraw dele."""
        mesa = _montar(tmp_path, hid="0003:054C:0DF2.001C", sob_uhid=True, extra="")
        assert mesa.ops().entradas_do_no("hidraw5") == []

    def test_nome_reciclado_para_um_teclado_nao_devolve_nada(self, tmp_path: Path) -> None:
        """Se o `hidrawN` virou o teclado dela entre o pedido e aqui, os nós
        de entrada seriam os do teclado. O broker não toca aparelho que não
        validou. A MORDIDA: tire o `_pai_hid_e_dualsense_fisico` do
        `entradas_do_no` e este teste devolve os nós do teclado."""
        mesa = _montar(tmp_path, hid="0005:3554:FA09.0002", extra="HID_PHYS=x\n")
        assert mesa.ops().entradas_do_no("hidraw5") == []

    def test_fechar_e_abrir_de_verdade(self, tmp_path: Path, acl_funciona: None) -> None:
        mesa = _montar(tmp_path)
        ops = mesa.ops()
        gamepad = mesa.dev_input / "event27"
        os.setxattr(gamepad, "system.posix_acl_access", encode_access_acl(UID))

        mudados, falhos = ops.fechar_entradas("hidraw5")

        assert falhos == []
        assert sorted(Path(n).name for n in mudados) == [
            "event27", "event28", "event29", "event30", "js1",
        ]
        for nome in ("event27", "event28", "event29", "event30", "js1"):
            assert _modo(mesa.dev_input / nome) == 0o600, nome
            assert _acl_do(mesa.dev_input / nome) == set(), nome
        assert _modo(mesa.dev_input / "js2") == 0o660, "o js do movimento é da regra 80"
        assert ops.entradas_abertas("hidraw5") == []

        # Reafirmar não é transição: o rehide de 30 s não enche o journal.
        assert ops.fechar_entradas("hidraw5") == ([], [])

        mudados, falhos = ops.abrir_entradas("hidraw5", UID)
        assert falhos == []
        assert len(mudados) == 5
        assert _modo(gamepad) == 0o660
        assert UID in _acl_do(gamepad)
        assert ops.entradas_fechadas_para("hidraw5", UID) == []
        assert ops.abrir_entradas("hidraw5", UID) == ([], [])

    def test_um_0600_com_acl_velha_conta_como_fechado(
        self, tmp_path: Path, acl_funciona: None
    ) -> None:
        """Num nó com ACL, os bits de grupo SÃO a máscara. `chmod 0600` sobre
        uma ACL de `user:ela:rw` deixa a entrada lá e sem valer nada."""
        mesa = _montar(tmp_path)
        no = mesa.dev_input / "event29"
        os.setxattr(no, "system.posix_acl_access", encode_access_acl(UID))
        no.chmod(0o600)
        abertas = mesa.ops().entradas_abertas("hidraw5")
        assert str(no) not in abertas


class TestOValidadorDoNoDeEntrada:
    @staticmethod
    def _stat_de_char(caminho: str) -> Any:
        """O nó de mentira visto como char device `0:0`, como o sysfs diz."""
        from types import SimpleNamespace

        os.stat(caminho)  # o arquivo tem de existir, como o nó real
        return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_rdev=os.makedev(0, 0))

    def _valida(self, mesa: Mesa, no: str) -> str | None:
        return validate_physical_input_node(
            no,
            dev_input_root=str(mesa.dev_input),
            sys_class_input=str(mesa.sys_input),
            sys_class_bluetooth=str(mesa.bluetooth),
            stat_fn=self._stat_de_char,
            lstat_fn=self._stat_de_char,
        )

    def test_o_fisico_pelo_radio_passa(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path)
        assert self._valida(mesa, f"{mesa.dev_input}/event29") == "event29"

    def test_o_fisico_pelo_cabo_passa(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path, hid="0003:054C:0CE6.0008", sob_uhid=False, extra="")
        assert self._valida(mesa, f"{mesa.dev_input}/event27") == "event27"

    def test_o_vpad_e_recusado_pela_topologia(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path, hid="0003:054C:0DF2.001C", extra="")
        assert self._valida(mesa, f"{mesa.dev_input}/event27") is None

    def test_o_vpad_e_recusado_pelas_marcas(self, tmp_path: Path) -> None:
        mesa = _montar(
            tmp_path,
            hid="0005:054C:0CE6.0006",
            extra="HID_PHYS=hefesto-vpad\nHID_UNIQ=02:fe:00:00:00:01\n",
        )
        assert self._valida(mesa, f"{mesa.dev_input}/event27") is None

    def test_js_nunca_e_servido(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path)
        assert self._valida(mesa, f"{mesa.dev_input}/js1") is None

    def test_caminho_torto_e_recusado(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path)
        assert self._valida(mesa, f"{mesa.dev_input}/../input/event27") is None
        assert self._valida(mesa, "/dev/hidraw5") is None

    def test_rdev_que_nao_casa_e_recusado(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path)
        (mesa.sys_input / "event27" / "dev").write_text("13:91\n", encoding="ascii")
        assert self._valida(mesa, f"{mesa.dev_input}/event27") is None


class TestOOpenDoNoDeEntrada:
    def test_serve_o_fd_do_fisico(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path)
        fd = mesa.ops().open_entrada(f"{mesa.dev_input}/event29", "event29")
        try:
            assert fd >= 0
        finally:
            os.close(fd)

    def test_o_eviocgid_de_outro_aparelho_e_recusado(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path)
        ops = mesa.ops()
        ops.input_id = (0x0005, 0x3554, 0xFA09, 1)
        with pytest.raises(StaleNodeError):
            ops.open_entrada(f"{mesa.dev_input}/event29", "event29")

    def test_o_vpad_pelo_cabo_e_recusado_mesmo_com_o_eviocgid_certo(
        self, tmp_path: Path
    ) -> None:
        """O EVIOCGID não separa o Edge físico do vpad (os dois são
        0003:054c:0df2). A MORDIDA: tire o `_e_o_nosso_vpad` do
        `open_entrada` e o broker serve o fd do controle que ele mesmo
        entrega ao jogo."""
        mesa = _montar(tmp_path, hid="0003:054C:0DF2.001C", extra="HID_PHYS=hefesto-vpad\n")
        ops = mesa.ops()
        ops.input_id = (0x0003, 0x054C, 0x0DF2, 1)
        with pytest.raises(StaleNodeError):
            ops.open_entrada(f"{mesa.dev_input}/event27", "event27")

    def test_rdev_trocado_depois_de_validar_e_recusado(self, tmp_path: Path) -> None:
        mesa = _montar(tmp_path)
        (mesa.sys_input / "event29" / "dev").write_text("13:77\n", encoding="ascii")
        with pytest.raises(StaleNodeError):
            mesa.ops().open_entrada(f"{mesa.dev_input}/event29", "event29")


# ---------------------------------------------------------------------------
# 3. A LEASE — os nós de entrada seguem o hidraw, e só o Nativo os devolve
# ---------------------------------------------------------------------------


class OpsComEntradas:
    """Dublê que MODELA os dois estados: o do hidraw e o dos nós de entrada.

    Responde `mudados` só na transição, como o de produção — um dublê que
    sempre dissesse «mudei» esconderia um laço que reescreve sem parar.
    """

    def __init__(self, *, entradas_abertas: bool = True) -> None:
        self.chamadas: list[tuple[Any, ...]] = []
        self.fechados: set[str] = set()
        self._abertas: dict[str, bool] = {}
        self._inicial = entradas_abertas
        self.fds: list[int] = []

    def _nos(self, base: str) -> list[str]:
        return [f"/dev/input/event-de-{base}"]

    def hide(self, node: str, base: str) -> None:
        self.chamadas.append(("hide", node))
        self.fechados.add(node)

    def restore(self, node: str, base: str, uid: int) -> None:
        self.chamadas.append(("restore", node))
        self.fechados.discard(node)

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return node not in self.fechados

    def open_node(self, node: str, base: str) -> int:  # pragma: no cover
        raise AssertionError("o open do hidraw não pertence a esta suíte")

    def aberta(self, base: str) -> bool:
        return self._abertas.get(base, self._inicial)

    def fechar_entradas(self, base: str) -> tuple[list[str], list[str]]:
        self.chamadas.append(("fechar_entradas", base))
        antes = self.aberta(base)
        self._abertas[base] = False
        return (self._nos(base) if antes else [], [])

    def abrir_entradas(self, base: str, uid: int) -> tuple[list[str], list[str]]:
        self.chamadas.append(("abrir_entradas", base))
        antes = self.aberta(base)
        self._abertas[base] = True
        return ([] if antes else self._nos(base), [])

    def entradas_abertas(self, base: str) -> list[str]:
        return self._nos(base) if self.aberta(base) else []

    def entradas_fechadas_para(self, base: str, uid: int) -> list[str]:
        return [] if self.aberta(base) else self._nos(base)

    def open_entrada(self, node: str, base: str) -> int:
        self.chamadas.append(("open_entrada", node, base))
        fd = os.open(os.devnull, os.O_RDONLY | os.O_CLOEXEC)
        self.fds.append(fd)
        return fd


def _validador(node: str) -> str | None:
    base = node.rsplit("/", 1)[-1]
    return base if base in {"hidraw3", "hidraw7"} else None


def _validador_de_entrada(node: str) -> str | None:
    base = node.rsplit("/", 1)[-1]
    return base if base in {"event27", "event29"} else None


def _estado(**kw: Any) -> tuple[BrokerState, OpsComEntradas, list[tuple[Any, ...]]]:
    ops = kw.pop("ops", OpsComEntradas())
    diario: list[tuple[Any, ...]] = []
    st = BrokerState(
        allowed_uid=UID,
        ops=ops,
        validator=_validador,
        validator_entrada=_validador_de_entrada,
        log=lambda evento, **campos: diario.append((evento, campos)),
        sleep_fn=lambda _s: None,
        **kw,
    )
    return st, ops, diario


def _pede(st: BrokerState, conn: int, payload: dict[str, Any]) -> dict[str, Any]:
    resposta, fd = st.handle_line(conn, UID, json.dumps(payload).encode())
    if fd is not None:
        os.close(fd)
    return dict(resposta)


class TestAsEntradasSeguemALease:
    def test_o_hide_fecha_os_nos_de_entrada(self) -> None:
        """A MORDIDA: tire o `_entradas_seguem` do `hide` e o
        `hidraw_broker_hidden` sai com os quatro nós abertos — o «0 de 1» do
        doctor de volta."""
        st, ops, diario = _estado(no_nasce_fechado=True)
        assert _pede(st, 1, {"cmd": "hide", "node": "/dev/hidraw3"})["ok"]
        assert not ops.aberta("hidraw3")
        transicao = {"node": "/dev/hidraw3", "nos": "/dev/input/event-de-hidraw3"}
        assert ("entradas_fechadas", transicao) in diario

    def test_a_exposicao_transitoria_nao_abre_os_nos_de_entrada(self) -> None:
        """O `hidapi` do handle de controle precisa do hidraw por caminho, e
        de mais nada. A MORDIDA: faça o `expose` sem o campo abrir as
        entradas e esta régua reprova — a janela da Steam volta pelo evdev."""
        st, ops, _ = _estado(no_nasce_fechado=True)
        resposta = _pede(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        assert resposta["state"] == "exposed"
        assert "/dev/hidraw3" not in ops.fechados
        assert not ops.aberta("hidraw3")

    def test_so_o_pedido_do_nativo_devolve_os_quatro(self) -> None:
        st, ops, _ = _estado(no_nasce_fechado=True)
        _pede(st, 1, {"cmd": "expose", "node": "/dev/hidraw3", "entradas": True})
        assert ops.aberta("hidraw3")
        assert _pede(st, 1, {"cmd": "status"})["entradas_expostas"] == ["/dev/hidraw3"]

        _pede(st, 1, {"cmd": "unexpose", "node": "/dev/hidraw3"})
        assert not ops.aberta("hidraw3")
        assert "/dev/hidraw3" in ops.fechados
        assert _pede(st, 1, {"cmd": "status"})["entradas_expostas"] == []

    def test_o_daemon_que_morre_no_nativo_fecha_tudo(self) -> None:
        """O EOF da lease: no mundo em que o nó nasce fechado, abrir tudo no
        EOF seria entregar o físico à Steam no instante em que o daemon caiu."""
        st, ops, _ = _estado(no_nasce_fechado=True)
        _pede(st, 1, {"cmd": "expose", "node": "/dev/hidraw3", "entradas": True})
        st.on_conn_closed(1)
        assert not ops.aberta("hidraw3")
        assert "/dev/hidraw3" in ops.fechados

    def test_o_pedido_explicito_vence_o_hide_de_outra_conexao(self) -> None:
        """Dois daemons em takeover: o do Nativo pediu os nós, o outro
        esconde. O pedido EXPLÍCITO vence (O-NO-NASCE-FECHADO-01), e quando
        ele morre o hide que sobra fecha."""
        st, ops, _ = _estado(no_nasce_fechado=True)
        _pede(st, 1, {"cmd": "expose", "node": "/dev/hidraw3", "entradas": True})
        _pede(st, 2, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert ops.aberta("hidraw3")
        assert "/dev/hidraw3" not in ops.fechados
        st.on_conn_closed(1)
        assert not ops.aberta("hidraw3")
        # HIDE-SO-O-HIDRAW-03: o hidraw fecha junto com as entradas. Esta
        # linha conferia só as entradas, e passava com o hidraw aberto até o
        # rehide de 30 s.
        assert "/dev/hidraw3" in ops.fechados

    def test_no_mundo_historico_o_restore_devolve_os_nos(self) -> None:
        """`--no-fechar-o-no`: o repouso é aberto, e os nós voltam com o
        hidraw quando o grab solta."""
        st, ops, _ = _estado(no_nasce_fechado=False)
        _pede(st, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert not ops.aberta("hidraw3")
        _pede(st, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert ops.aberta("hidraw3")

    def test_no_mundo_da_cura_o_restore_mantem_fechado(self) -> None:
        st, ops, _ = _estado(no_nasce_fechado=True)
        _pede(st, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        _pede(st, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert not ops.aberta("hidraw3")

    def test_recusa_nao_toca_nos_de_entrada(self) -> None:
        st, ops, _ = _estado(no_nasce_fechado=True)
        _pede(st, 1, {"cmd": "hide", "node": "/dev/hidraw9"})
        _pede(st, 1, {"cmd": "hide", "node": "/tmp/hidraw3"})
        assert not any(c[0].endswith("_entradas") for c in ops.chamadas)

    def test_dublê_antigo_sem_mecanica_de_entrada_segue_funcionando(self) -> None:
        """Os dublês da suíte de antes modelam um aparelho sem nós de
        entrada; o broker não pode quebrar sobre eles."""

        class OpsAntigo:
            def hide(self, node: str, base: str) -> None:
                pass

            def restore(self, node: str, base: str, uid: int) -> None:
                pass

            def is_exposed_to(self, node: str, uid: int) -> bool:
                return True

        st = BrokerState(
            allowed_uid=UID, ops=OpsAntigo(), validator=_validador, log=lambda *a, **k: None,
            no_nasce_fechado=True,
        )
        resposta, _ = st.handle_line(1, UID, b'{"cmd": "hide", "node": "/dev/hidraw3"}')
        assert resposta["ok"] is True


class TestOOpenServeOEvdevDoFisico:
    def test_o_fd_do_evdev_sai_pelo_open(self) -> None:
        st, ops, _ = _estado(no_nasce_fechado=True)
        resposta, fd = st.handle_line(
            1, UID, json.dumps({"cmd": "open", "node": "/dev/input/event29"}).encode()
        )
        try:
            assert resposta == {
                "ok": True, "cmd": "open", "node": "/dev/input/event29", "state": "entrada",
            }
            assert fd is not None and fd >= 0
            assert ("open_entrada", "/dev/input/event29", "event29") in ops.chamadas
        finally:
            if fd is not None:
                os.close(fd)

    def test_no_de_entrada_que_nao_valida_e_recusado(self) -> None:
        st, ops, _ = _estado()
        resposta, fd = st.handle_line(
            1, UID, json.dumps({"cmd": "open", "node": "/dev/input/event99"}).encode()
        )
        assert fd is None
        assert resposta["error"] == "reject_not_physical_dualsense"
        assert not any(c[0] == "open_entrada" for c in ops.chamadas)

    def test_js_e_caminho_torto_caem_na_recusa_do_hidraw(self) -> None:
        st, _, _ = _estado()
        for torto in ("/dev/input/js1", "/dev/input/../hidraw3", "/dev/input/event1x"):
            resposta, fd = st.handle_line(
                1, UID, json.dumps({"cmd": "open", "node": torto}).encode()
            )
            assert fd is None and resposta["ok"] is False, torto


# ---------------------------------------------------------------------------
# 4. OS BASELINES — o que abre ao parar e o que fecha ao subir
# ---------------------------------------------------------------------------


def _lista(tmp_path: Path, *bases: str) -> Path:
    """Um `/sys/class/hidraw` que só serve para o `listdir` dos baselines."""
    pasta = tmp_path / "sys-class-hidraw"
    for base in bases:
        (pasta / base).mkdir(parents=True, exist_ok=True)
    return pasta


class TestOsBaselinesLevamOsNosDeEntrada:
    def test_o_start_fecha_os_nos_que_nasceram_abertos(self, tmp_path: Path) -> None:
        """O controle que conectou antes do socket existir nasceu aberto.
        A MORDIDA: tire o bloco das entradas do `fechar_todo_fisico` e o
        cabo plugado no boot fica visível ao jogo até o replug."""
        ops = OpsComEntradas(entradas_abertas=True)
        ops.fechados.add("/dev/hidraw3")  # o hidraw já nasceu fechado pela 70
        fechar_todo_fisico(
            uid=UID, ops=ops, dev_root="/dev", sys_class_hidraw=str(_lista(tmp_path, "hidraw3")),
            validator=_validador, log=lambda *a, **k: None,
        )
        assert not ops.aberta("hidraw3")

    def test_o_piso_de_recuperacao_abre_os_nos_de_entrada(self, tmp_path: Path) -> None:
        ops = OpsComEntradas(entradas_abertas=False)
        restore_all_physical(
            uid=UID, ops=ops, dev_root="/dev", sys_class_hidraw=str(_lista(tmp_path, "hidraw3")),
            validator=_validador, log=lambda *a, **k: None,
        )
        assert ops.aberta("hidraw3")


# ---------------------------------------------------------------------------
# 5. O REINÍCIO QUE NÃO ABRE — o achado do install de 24/09
# ---------------------------------------------------------------------------


class TestOReinicioPedidoNaoAbre:
    def _pedido(self, tmp_path: Path, *, modo: int = 0o644, idade: float = 0.0) -> Path:
        arquivo = tmp_path / "reinicio-sem-abrir"
        arquivo.write_text("", encoding="ascii")
        arquivo.chmod(modo)
        quando = time.time() - idade
        os.utime(arquivo, (quando, quando))
        return arquivo

    def test_o_pedido_recente_do_dono_vale(self, tmp_path: Path) -> None:
        arquivo = self._pedido(tmp_path)
        assert reinicio_sem_abrir_pedido(str(arquivo), dono_esperado=UID) is True

    def test_pedido_velho_e_lixo(self, tmp_path: Path) -> None:
        """Um install que caiu no meio não pode calar o piso de recuperação."""
        arquivo = self._pedido(tmp_path, idade=hb.REINICIO_SEM_ABRIR_VALIDADE_S + 30)
        assert reinicio_sem_abrir_pedido(str(arquivo), dono_esperado=UID) is False

    def test_pedido_que_outro_escreveria_nao_vale(self, tmp_path: Path) -> None:
        arquivo = self._pedido(tmp_path, modo=0o666)
        assert reinicio_sem_abrir_pedido(str(arquivo), dono_esperado=UID) is False

    def test_pedido_de_outro_dono_nao_vale(self, tmp_path: Path) -> None:
        arquivo = self._pedido(tmp_path)
        assert reinicio_sem_abrir_pedido(str(arquivo), dono_esperado=UID + 1) is False

    def test_sem_pedido_nao_vale(self, tmp_path: Path) -> None:
        assert reinicio_sem_abrir_pedido(str(tmp_path / "nada"), dono_esperado=UID) is False

    def test_o_broker_que_sai_num_reinicio_pedido_nao_abre(self) -> None:
        """A MORDIDA: tire o `if ... self._reinicio_sem_abrir()` do
        `restore_everything` e o broker que sai reabre o hidraw e os quatro
        nós no segundo em que a Steam vigia /dev."""
        st, ops, diario = _estado(no_nasce_fechado=True, reinicio_sem_abrir=lambda: True)
        _pede(st, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        ops.chamadas.clear()

        assert st.restore_everything() == []
        assert ops.chamadas == []
        assert "/dev/hidraw3" in ops.fechados
        assert any(evento == "reinicio_sem_abrir" for evento, _ in diario)

    def test_o_broker_que_para_de_verdade_abre_tudo(self) -> None:
        st, ops, _ = _estado(no_nasce_fechado=True, reinicio_sem_abrir=lambda: False)
        _pede(st, 1, {"cmd": "hide", "node": "/dev/hidraw3"})

        assert st.restore_everything() == ["/dev/hidraw3"]
        assert "/dev/hidraw3" not in ops.fechados
        assert ops.aberta("hidraw3")

    def test_o_broker_que_para_abre_as_entradas_do_no_so_exposto(self) -> None:
        """O nó que a conexão só EXPÔS (o `with` transitório do handle) tem o
        hidraw aberto e as entradas fechadas. O broker que para de verdade
        abre as entradas dele também. A MORDIDA (conferência): tire o laço dos
        `expostos` do `restore_everything` e elas ficam fechadas sem broker."""
        st, ops, _ = _estado(no_nasce_fechado=True, reinicio_sem_abrir=lambda: False)
        _pede(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        assert not ops.aberta("hidraw3")

        st.restore_everything()
        assert ops.aberta("hidraw3")

    def test_no_mundo_historico_o_pedido_nao_muda_nada(self) -> None:
        """Sem a cura instalada o nó nasce aberto, e abrir ao parar é só
        voltar ao estado de nascimento."""
        st, ops, _ = _estado(no_nasce_fechado=False, reinicio_sem_abrir=lambda: True)
        _pede(st, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert st.restore_everything() == ["/dev/hidraw3"]
        assert ops.aberta("hidraw3")

    def test_o_execstoppost_do_reinicio_pedido_nao_abre(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chamadas: list[str] = []

        def _restore_all(**_kw: Any) -> list[str]:
            chamadas.append("restore")
            return []

        monkeypatch.setenv(hb.ALLOWED_UID_ENV, "1000")
        monkeypatch.setenv(hb.NO_NASCE_FECHADO_ENV, "1")
        monkeypatch.setattr(hb, "reinicio_sem_abrir_pedido", lambda *a, **k: True)
        monkeypatch.setattr(hb, "restore_all_physical", _restore_all)
        assert hb.main(["--restore-all-and-exit"]) == 0
        assert chamadas == []

        monkeypatch.setattr(hb, "reinicio_sem_abrir_pedido", lambda *a, **k: False)
        assert hb.main(["--restore-all-and-exit"]) == 0
        assert chamadas == ["restore"]
