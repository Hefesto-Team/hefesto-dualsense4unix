"""HIDE-SO-O-HIDRAW-03 — a conexão do Nativo que morre não deixa o físico à mostra.

O buraco que a HIDE-SO-O-HIDRAW-02 registrou e não curou (24/09/2026): com o
nó EXPOSTO por uma conexão (o Modo Nativo, que pede `expose` com
`"entradas": true`), o `hide` que chega por OUTRA conexão é ADIADO
(`hide_adiado_por_exposicao`): a lease dele fica registrada e o fs não é
tocado. Quando a conexão do Nativo morre, o `on_conn_closed` pulava todo nó
em `hidden` — e o hidraw ficava aberto, com o `status` dizendo «hidden», até
o próximo `hide` do daemon: o rehide do `reconnect_loop`, a cada 30 s. É a
janela em que a Steam aberta pega o físico (STEAM-NO-FISICO-01).

As duas conexões existem de verdade: dois daemons em takeover (o velho no
Nativo morrendo, o novo escondendo), e o MESMO daemon cujo cliente reconecta
depois de um timeout (a exposição ficou na lease velha, o `hide` saiu pela
nova antes de o broker ver o EOF da velha).

A régua usa a CLASSE REAL do broker (`BrokerState`, e o `Broker` com o
`HidrawBrokerClient` num socket de verdade) sobre a mecânica de fs REAL
(`FsAclOps`: `chmod` e a ACL por `/proc/self/fd`) e o validador REAL
(`validate_physical_node`). A única troca é «é char device?», que aceita
arquivo comum — a suíte não cria char device sem root. Nada aqui toca /dev,
o sysfs real ou o broker vivo.

A mesa é a de quatro: P1 e P2 pelo cabo, P3 e P4 pelo rádio.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import stat
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import (
    Broker,
    BrokerState,
    FsAclOps,
    decode_acl_user_uids,
    encode_access_acl,
)
from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient

UID = os.getuid()
#: Faixas sintéticas da casa para fixture: nunca endereço real mascarado.
MAC_DO_ADAPTADOR = "aa:bb:cc:00:00:01"

#: (nó, transporte, HID_ID do pai, MAC do controle). O número do HID e o do
#: hidraw andam juntos só para quem lê o teste se achar.
CONTROLES = (
    ("hidraw3", "cabo", "0003:054C:0CE6.0003", ""),
    ("hidraw5", "cabo", "0003:054C:0CE6.0005", ""),
    ("hidraw7", "radio", "0005:054C:0CE6.0007", "e8:47:3a:00:00:07"),
    ("hidraw9", "radio", "0005:054C:0CE6.0009", "e8:47:3a:00:00:09"),
)


# ---------------------------------------------------------------------------
# A mesa de mentira — quatro DualSense, dois por transporte
# ---------------------------------------------------------------------------


@dataclass
class Mesa:
    dev: Path
    dev_input: Path
    sys_hidraw: Path
    sys_input: Path
    bluetooth: Path

    def no(self, base: str) -> str:
        return f"{self.dev}/{base}"

    @property
    def nos(self) -> list[str]:
        return [self.no(base) for base, *_ in CONTROLES]

    def entradas(self, base: str) -> list[Path]:
        numero = int(base.removeprefix("hidraw"))
        return [self.dev_input / f"event{numero}{i}" for i in range(3)] + [
            self.dev_input / f"js{numero}0"
        ]


class _StatQueAceitaArquivo(ModuleType):
    """O módulo `stat` com UMA troca: o `S_ISCHR` aceita arquivo comum.

    Só o `hidraw_broker` o recebe (monkeypatch no atributo `stat_mod` dele),
    e só enquanto o teste vive. O validador, o `_pin` do hide/restore e o
    cruzamento do rdev contra o sysfs continuam os de produção.
    """

    def __init__(self) -> None:
        super().__init__("stat")

    def __getattr__(self, nome: str) -> Any:
        return getattr(stat, nome)

    @staticmethod
    def S_ISCHR(modo: int) -> bool:  # noqa: N802 - espelha o nome do stdlib
        return stat.S_ISCHR(modo) or stat.S_ISREG(modo)


class _OpsDeArquivo(FsAclOps):
    """O `FsAclOps` de produção; o «é char device?» das entradas aceita arquivo.

    `falhar_o_hide` só existe para fabricar o nó ÓRFÃO do Achado Onda S #3 (o
    fs que falha no EOF da lease): desligado, que é o padrão, o `hide` é o de
    produção.
    """

    _e_char_device = staticmethod(stat.S_ISREG)
    falhar_o_hide = False

    def hide(self, node: str, base: str) -> None:
        if self.falhar_o_hide:
            raise PermissionError(node)
        super().hide(node, base)


def _montar(raiz: Path) -> Mesa:
    """Quatro DualSense com os nós de entrada, os dois do rádio sob o uhid."""
    mesa = Mesa(
        dev=raiz / "dev",
        dev_input=raiz / "dev" / "input",
        sys_hidraw=raiz / "sys" / "class" / "hidraw",
        sys_input=raiz / "sys" / "class" / "input",
        bluetooth=raiz / "sys" / "class" / "bluetooth",
    )
    for pasta in (mesa.dev_input, mesa.sys_hidraw, mesa.sys_input):
        pasta.mkdir(parents=True, exist_ok=True)
    (mesa.bluetooth / "hci0").mkdir(parents=True)
    (mesa.bluetooth / "hci0" / "address").write_text(MAC_DO_ADAPTADOR + "\n", encoding="ascii")
    for base, transporte, hid, mac in CONTROLES:
        if transporte == "radio":
            topo = raiz / "sys" / "devices" / "virtual" / "misc" / "uhid"
            extra = f"HID_PHYS={MAC_DO_ADAPTADOR}\nHID_UNIQ={mac}\n"
        else:
            porta = base.removeprefix("hidraw")
            topo = raiz / "sys" / "devices" / "pci0000:00" / "usb1" / f"1-{porta}"
            extra = ""
        hid_dir = topo / hid
        hid_dir.mkdir(parents=True)
        bus, vendor, produto = hid[:4], hid[5:9], hid[10:14]
        (hid_dir / "uevent").write_text(
            f"DRIVER=playstation\nHID_ID={bus}:0000{vendor}:0000{produto}\n"
            f"HID_NAME=x\n{extra}",
            encoding="ascii",
        )
        (mesa.sys_hidraw / base).mkdir()
        (mesa.sys_hidraw / base / "dev").write_text("0:0\n", encoding="ascii")
        (mesa.sys_hidraw / base / "device").symlink_to(hid_dir)
        no = mesa.dev / base
        no.write_text("", encoding="ascii")
        no.chmod(0o600)  # o físico nasce fechado (a regra 70 da cura)
        numero = int(base.removeprefix("hidraw"))
        filhos_por_input = (
            ("DualSense Wireless Controller", (f"event{numero}0", f"js{numero}0")),
            ("DualSense Wireless Controller Motion Sensors", (f"event{numero}1",)),
            ("DualSense Wireless Controller Touchpad", (f"event{numero}2",)),
        )
        for i, (nome, filhos) in enumerate(filhos_por_input):
            d = hid_dir / "input" / f"input{numero}{i}"
            d.mkdir(parents=True)
            (d / "name").write_text(nome + "\n", encoding="utf-8")
            for filho in filhos:
                (d / filho).mkdir()
                (d / filho / "dev").write_text("0:0\n", encoding="ascii")
                (mesa.sys_input / filho).symlink_to(d / filho)
                entrada = mesa.dev_input / filho
                entrada.write_text("", encoding="ascii")
                entrada.chmod(0o600)  # a regra 72 da HIDE-02
    # E o NOSSO vpad, que o validador recusa: USB sob o uhid.
    vpad = raiz / "sys" / "devices" / "virtual" / "misc" / "uhid" / "0003:054C:0DF2.0004"
    vpad.mkdir(parents=True)
    (vpad / "uevent").write_text(
        "HID_ID=0003:0000054C:00000DF2\nHID_NAME=x\n", encoding="ascii"
    )
    (mesa.sys_hidraw / "hidraw4").mkdir()
    (mesa.sys_hidraw / "hidraw4" / "dev").write_text("0:0\n", encoding="ascii")
    (mesa.sys_hidraw / "hidraw4" / "device").symlink_to(vpad)
    (mesa.dev / "hidraw4").write_text("", encoding="ascii")
    return mesa


def _aberto_para_ela(caminho: str | Path) -> bool:
    """O estado canônico exposto, lido do fs: `0660` + ACL do uid dela."""
    try:
        modo = stat.S_IMODE(os.stat(caminho).st_mode)
        acl = decode_acl_user_uids(os.getxattr(caminho, "system.posix_acl_access"))
    except OSError:
        return False
    return modo == 0o660 and UID in acl


def _fechado(caminho: str | Path) -> bool:
    """`0600 root` no nosso mundo: ninguém além do dono, e ACL nenhuma."""
    modo = stat.S_IMODE(os.stat(caminho).st_mode)
    try:
        acl = os.getxattr(caminho, "system.posix_acl_access")
    except OSError:
        acl = b""
    return modo == 0o600 and not acl


@pytest.fixture
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mesa:
    sonda = tmp_path / "sonda-de-acl"
    sonda.write_text("", encoding="ascii")
    try:
        os.setxattr(sonda, "system.posix_acl_access", encode_access_acl(UID))
    except OSError as exc:  # pragma: no cover - depende do fs do CI
        pytest.skip(f"o fs de teste não guarda ACL POSIX: {exc}")
    finally:
        sonda.unlink()
    monkeypatch.setattr(hb, "stat_mod", _StatQueAceitaArquivo())
    return _montar(tmp_path)


def _estado(
    mesa: Mesa, diario: list[tuple[str, dict[str, Any]]], *, no_nasce_fechado: bool = True
) -> BrokerState:
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
        no_nasce_fechado=no_nasce_fechado,
    )


def _pede(st: BrokerState, conn: int, payload: dict[str, Any]) -> dict[str, Any]:
    resposta, fd = st.handle_line(conn, UID, json.dumps(payload).encode())
    if fd is not None:
        os.close(fd)
    return dict(resposta)


#: As duas conexões do defeito. NATIVO pede os nós abertos (o `expose` do
#: `_reconciliar_exposicao_do_modo_nativo`, com as entradas); OUTRA esconde (o
#: rehide do daemon novo num takeover, ou a lease nova do mesmo daemon).
NATIVO, OUTRA = 1, 2


# ---------------------------------------------------------------------------
# 1. A classe real, conexão por conexão
# ---------------------------------------------------------------------------


class TestAConexaoDoNativoQueMorre:
    def test_a_validacao_e_a_de_producao_nos_dois_transportes(self, mesa: Mesa) -> None:
        """A mesa é real para o validador: se ele recusasse um transporte, a
        régua de baixo passaria por não fazer nada nele. E ele segue
        recusando o nosso vpad, que mora na mesma mesa."""
        st = _estado(mesa, [])
        for no in mesa.nos:
            assert _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})["ok"], no
            assert _aberto_para_ela(no), no
            assert all(_aberto_para_ela(e) for e in mesa.entradas(no.rsplit("/", 1)[-1])), no
        assert _pede(st, NATIVO, {"cmd": "expose", "node": mesa.no("hidraw4")})[
            "error"
        ] == "reject_not_physical_dualsense"

    def test_os_quatro_voltam_a_esconder_na_hora(self, mesa: Mesa) -> None:
        """A MORDIDA: devolva o `or canon in self.hidden` ao laço dos
        `expostos_da_conn` do `on_conn_closed` e os quatro hidraw ficam
        `0660` + ACL dela depois do EOF — só o rehide de 30 s os fechava."""
        diario: list[tuple[str, dict[str, Any]]] = []
        st = _estado(mesa, diario)
        for no in mesa.nos:
            _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        for no in mesa.nos:
            resposta = _pede(st, OUTRA, {"cmd": "hide", "node": no})
            # O pedido explícito do Nativo vence enquanto a conexão dele vive.
            assert resposta["state"] == "exposed", no
            assert _aberto_para_ela(no), no
        assert sum(1 for e, _ in diario if e == "hide_adiado_por_exposicao") == 4

        st.on_conn_closed(NATIVO)

        for base, transporte, *_ in CONTROLES:
            assert _fechado(mesa.no(base)), f"{base} ({transporte}) ficou à mostra"
            for entrada in mesa.entradas(base):
                assert _fechado(entrada), f"{entrada} ({transporte})"
        assert sum(1 for e, _ in diario if e == "hide_adiado_cumprido") == 4
        # O `status` e o fs contam a mesma história: escondido É fechado.
        status = _pede(st, OUTRA, {"cmd": "status"})
        assert status["hidden"] == sorted(mesa.nos)
        assert status["expostos"] == [] and status["entradas_expostas"] == []

    def test_a_outra_lease_segue_dona_do_no(self, mesa: Mesa) -> None:
        """Depois do EOF o nó é da lease que o esconde: soltá-la devolve o
        repouso, e o daemon que morre depois não deixa nada para trás."""
        st = _estado(mesa, [])
        no = mesa.no("hidraw7")
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, OUTRA, {"cmd": "hide", "node": no})
        st.on_conn_closed(NATIVO)
        assert _pede(st, OUTRA, {"cmd": "restore", "node": no})["state"] == "fechado"
        st.on_conn_closed(OUTRA)
        assert _fechado(no)
        assert st.hidden == {} and st.expostos == {}

    def test_o_nativo_com_hide_proprio_e_a_outra_lease(self, mesa: Mesa) -> None:
        """A conexão do Nativo também escondera o nó (refcount 2): o primeiro
        laço só desconta a lease dela e segue, sem tocar o fs. A MORDIDA é a
        mesma do teste acima, pelo outro caminho."""
        st = _estado(mesa, [])
        no = mesa.no("hidraw3")
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, NATIVO, {"cmd": "hide", "node": no})
        _pede(st, OUTRA, {"cmd": "hide", "node": no})
        assert st.hidden[no].refcount == 2
        st.on_conn_closed(NATIVO)
        assert _fechado(no)
        assert st.hidden[no].refcount == 1

    def test_sem_a_regra_da_cura_tambem(self, mesa: Mesa) -> None:
        """«Para qualquer computador»: no mundo histórico (`--no-fechar-o-no`)
        o nó nasce aberto, mas quem o esconde é a lease viva — e ela manda."""
        st = _estado(mesa, [], no_nasce_fechado=False)
        no = mesa.no("hidraw9")
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, OUTRA, {"cmd": "hide", "node": no})
        st.on_conn_closed(NATIVO)
        assert _fechado(no)


class TestACuraNaoFechaDemais:
    def test_outro_nativo_vivo_segura_o_no_aberto(self, mesa: Mesa) -> None:
        """Dois pedidos explícitos: morrer um não fecha o nó do outro."""
        st = _estado(mesa, [])
        no = mesa.no("hidraw5")
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, 3, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, OUTRA, {"cmd": "hide", "node": no})
        st.on_conn_closed(NATIVO)
        assert _aberto_para_ela(no)
        assert all(_aberto_para_ela(e) for e in mesa.entradas("hidraw5"))
        st.on_conn_closed(3)
        assert _fechado(no)

    def test_quem_morre_primeiro_e_o_hide(self, mesa: Mesa) -> None:
        """O Nativo segue de pé: o nó segue aberto para o jogo. Quando ele
        morre depois, não sobra hide nenhum a cumprir: o nó fecha pelo
        repouso, e o diário não diz «hide adiado cumprido». A MORDIDA: faça
        o `adiado` do `on_conn_closed` valer sempre e a linha sai aqui."""
        diario: list[tuple[str, dict[str, Any]]] = []
        st = _estado(mesa, diario)
        no = mesa.no("hidraw7")
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, OUTRA, {"cmd": "hide", "node": no})
        st.on_conn_closed(OUTRA)
        assert _aberto_para_ela(no)
        st.on_conn_closed(NATIVO)
        assert _fechado(no)
        assert not any(e == "hide_adiado_cumprido" for e, _ in diario)

    def test_o_orfao_que_o_nativo_expos_volta_ao_repouso(self, mesa: Mesa) -> None:
        """Um nó ÓRFÃO — a lease que o escondeu morreu com o fs falho e ele
        ficou em `hidden` sem dono (Achado Onda S #3) — que o Nativo expôs.
        Sem lease de hide viva, o destino é o de nascimento: fechado com a
        regra da cura. Antes o laço pulava todo nó em `hidden`, e o órfão
        ficava aberto sem ninguém que o fechasse (o daemon no Nativo não
        esconde). E ele não é hide adiado: o diário não diz «cumprido».
        As MORDIDAS: pule o órfão no laço e o nó fica à mostra; conte o
        órfão como adiado e a linha do diário mente."""
        diario: list[tuple[str, dict[str, Any]]] = []
        st = _estado(mesa, diario)
        ops = st._ops
        assert isinstance(ops, _OpsDeArquivo)
        no = mesa.no("hidraw5")
        _pede(st, OUTRA, {"cmd": "hide", "node": no})
        ops.falhar_o_hide = True
        st.on_conn_closed(OUTRA)  # o fs falha: o nó fica órfão em `hidden`
        ops.falhar_o_hide = False
        assert no in st.hidden and st._lease_holders(no) == 0
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        assert _aberto_para_ela(no)
        st.on_conn_closed(NATIVO)
        assert _fechado(no), "o órfão que o Nativo expôs ficou à mostra"
        assert all(_fechado(e) for e in mesa.entradas("hidraw5"))
        assert not any(e == "hide_adiado_cumprido" for e, _ in diario)

    def test_o_no_que_sumiu_nao_vira_cumprido(self, mesa: Mesa) -> None:
        """O controle saiu da mesa antes do EOF: não há o que fechar, e o
        diário não diz que fechou. A MORDIDA: tire o `state == "fechado"` do
        `hide_adiado_cumprido` e ele sai para um nó que nem existe."""
        diario: list[tuple[str, dict[str, Any]]] = []
        st = _estado(mesa, diario)
        no = mesa.no("hidraw9")
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, OUTRA, {"cmd": "hide", "node": no})
        os.unlink(no)
        st.on_conn_closed(NATIVO)
        assert not any(e == "hide_adiado_cumprido" for e, _ in diario)

    def test_cada_no_vai_ao_repouso_uma_vez(self, mesa: Mesa) -> None:
        """A MESMA conexão expôs e escondeu: o EOF devolve o nó UMA vez. A
        MORDIDA: tire o `ja_no_repouso` e ele sai duas vezes na lista (e no
        `lease_closed_restored` do diário), com dois `chmod` no nó."""
        diario: list[tuple[str, dict[str, Any]]] = []
        st = _estado(mesa, diario)
        no = mesa.no("hidraw3")
        _pede(st, NATIVO, {"cmd": "expose", "node": no, "entradas": True})
        _pede(st, NATIVO, {"cmd": "hide", "node": no})
        assert st.on_conn_closed(NATIVO) == [no]
        assert _fechado(no)
        assert sum(1 for e, _ in diario if e == "node_em_repouso_fechado") == 1


# ---------------------------------------------------------------------------
# 2. Ponta a ponta: o broker num socket de verdade e dois clientes de verdade
# ---------------------------------------------------------------------------


def _pasta_curta(tmp_path: Path) -> str:
    """`sun_path` tem ~108 bytes; o tmp do berço pode passar disso."""
    candidato = tmp_path / "bk"
    if len(str(candidato / "broker.sock")) <= 90:
        candidato.mkdir(exist_ok=True)
        return str(candidato)
    return tempfile.mkdtemp(prefix="hefesto-bk-hide03-", dir="/tmp")


def _espera(cond: Callable[[], bool], timeout: float = 2.0) -> bool:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


@pytest.fixture
def broker_vivo(mesa: Mesa, tmp_path: Path) -> Any:
    pasta = _pasta_curta(tmp_path)
    caminho = os.path.join(pasta, "broker.sock")
    escuta = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    escuta.bind(caminho)
    escuta.listen(4)
    diario: list[tuple[str, dict[str, Any]]] = []
    st = _estado(mesa, diario)
    broker = Broker(st, escuta, log=lambda *a, **k: None)
    fio = threading.Thread(target=broker.run, daemon=True)
    fio.start()
    try:
        yield caminho, st, diario
    finally:
        broker.stopping = True
        with (
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as cutuca,
            contextlib.suppress(OSError),
        ):
            cutuca.connect(caminho)
        fio.join(timeout=3.0)
        escuta.close()
        if os.path.exists(caminho):
            os.unlink(caminho)
        if pasta.startswith("/tmp/hefesto-bk-hide03-"):
            os.rmdir(pasta)


class TestPontaAPonta:
    def test_o_cliente_do_nativo_cai_e_o_broker_esconde_no_tique_seguinte(
        self, mesa: Mesa, broker_vivo: Any
    ) -> None:
        """O EOF de verdade: o `close()` do cliente do Nativo é o que o kernel
        faz quando o daemon morre. A outra lease não pede mais nada — quem
        fecha os quatro é o broker, no passo em que vê o EOF. A MORDIDA: a
        mesma do `on_conn_closed`; os quatro seguem abertos até o prazo."""
        caminho, _st, diario = broker_vivo
        nativo = HidrawBrokerClient(caminho)
        outra = HidrawBrokerClient(caminho)
        try:
            for no in mesa.nos:
                assert nativo.expor(no, entradas=True), no
            for no in mesa.nos:
                assert outra.hide(no), no
            assert all(_aberto_para_ela(no) for no in mesa.nos)

            nativo.close()

            # O fio do broker fecha os quatro hidraw e SÓ DEPOIS os nós de
            # entrada (o laço final do `on_conn_closed`): a espera cobre os
            # dois, senão a régua lê as entradas no meio do EOF e reprova o
            # produto certo quando o fio perde a vez entre um e outro.
            todos = [Path(no) for no in mesa.nos] + [
                e for base, *_ in CONTROLES for e in mesa.entradas(base)
            ]
            assert _espera(lambda: all(_fechado(n) for n in todos)), [
                str(n) for n in todos if not _fechado(n)
            ]
            status = outra.status()
            assert status is not None
            assert status["hidden"] == sorted(mesa.nos)
            assert status["expostos"] == []
            assert sum(1 for e, _ in diario if e == "hide_adiado_cumprido") == 4
        finally:
            nativo.close()
            outra.close()

    def test_o_diario_do_daemon_nao_diz_escondido_sobre_no_aberto(
        self, mesa: Mesa, broker_vivo: Any
    ) -> None:
        """O `hide` adiado responde `ok` com `state: "exposed"`: o nó segue
        aberto. O diário do daemon dizia `hidraw_broker_hidden` assim mesmo,
        e o `hidraw_broker_hidden` de verdade, depois do EOF, virava
        reafirmação em `debug` — sumia do journal justamente a transição.
        A MORDIDA: devolva o `hidraw_broker_hidden` incondicional ao `hide`
        do cliente e esta régua reprova."""
        caminho, _st, _diario = broker_vivo
        nativo = HidrawBrokerClient(caminho)
        outra = HidrawBrokerClient(caminho)
        no = mesa.no("hidraw7")
        try:
            assert nativo.expor(no, entradas=True)
            with structlog.testing.capture_logs() as adiado:
                assert outra.hide(no)
            assert _aberto_para_ela(no)
            eventos = [r["event"] for r in adiado]
            assert "hidraw_broker_hidden" not in eventos, eventos
            assert "hidraw_broker_hide_adiado" in eventos, eventos

            nativo.close()
            assert _espera(lambda: _fechado(no))
            with structlog.testing.capture_logs() as depois:
                assert outra.hide(no)  # o rehide do daemon, já sem o Nativo
            info = [r["event"] for r in depois if r.get("log_level") == "info"]
            assert "hidraw_broker_hidden" in info, depois
        finally:
            nativo.close()
            outra.close()
