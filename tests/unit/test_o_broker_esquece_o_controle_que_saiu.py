"""O-BROKER-ESQUECE-O-CONTROLE-QUE-SAIU-01 — a lease é do aparelho, e não do nome.

A bancada de 29/09 (S.3, 03:44 e 03:55): os quatro DualSense no rádio, os
quatro pads `uhid`, e o doctor acusando de FÍSICO cinco nós de entrada que eram
do pad do P2. O quinto nome do `status` do broker era o `hidraw6`, que o
vermelho (o P1) usava até sair às 02:50:06. O primário que sai só reserva o
posto, ninguém pediu o `restore` daquele nome, e a conexão do daemon (a lease)
seguiu viva. O kernel deu o `hidraw6` ao pad do P2, e o broker passou a dizer
«escondido» sobre ele.

A cura (a `D-2909-A-LEASE-E-DO-APARELHO`, por delegação): a lease guarda o pai
HID do nó no pedido, e antes de todo pedido e no EOF o broker compara o pai de
agora com o guardado. Mudou ou sumiu, a lease acaba, sem tocar no fs. Sysfs
mudo (`None`) não poda.

A MESA DE MENTIRA é a da `test_o_broker_nao_reescreve_o_que_nao_mudou.py`: o
`BrokerState`, o `FsAclOps` e o validador são os de produção, pedidos pelo
`handle_line`, sobre um `/sys` e um `/dev` em `tmp_path`. A única troca é
«é char device?», que aceita arquivo comum (a suíte não cria char device sem
root). O `dev` de todo nó é `0:0`, antes e depois da troca de aparelho: é o
caso de 29/09, em que o `hidraw6` do pad tinha o mesmo `maior:menor` do
vermelho, e é o que faz o rdev não servir de identidade.

Cada régua diz a sua MORDIDA; as da 1 e da 8 rodam aqui dentro.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import (
    BrokerState,
    FsAclOps,
    encode_access_acl,
)

UID = os.getuid()
ACL = "system.posix_acl_access"
#: Faixas sintéticas da casa para fixture: nunca endereço real mascarado.
MAC_DO_ADAPTADOR = "aa:bb:cc:00:00:01"

#: As conexões: o daemon (a lease que vive enquanto ele vive), o Modo Nativo e
#: um segundo daemon em takeover.
DAEMON = 7
NATIVO = 3
OUTRA = 8

#: A cena de 29/09: os quatro físicos pelo rádio que seguiram na mesa, e o
#: `hidraw6` do vermelho, o P1 que saiu.
OS_QUATRO = ("hidraw5", "hidraw7", "hidraw9", "hidraw10")
O_DO_P1 = "hidraw6"

EVENTO = "lease_do_aparelho_que_saiu"


# ---------------------------------------------------------------------------
# A mesa de mentira: aparelhos que nascem, saem e trocam de nome
# ---------------------------------------------------------------------------


@dataclass
class Aparelho:
    base: str
    hid: str
    hid_dir: Path
    entradas: list[Path]


class Mesa:
    """O `/sys` e o `/dev` de mentira, e o `<seq>` do kernel, que só cresce."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.dev = raiz / "dev"
        self.dev_input = self.dev / "input"
        self.sys_hidraw = raiz / "sys" / "class" / "hidraw"
        self.sys_input = raiz / "sys" / "class" / "input"
        self.bluetooth = raiz / "sys" / "class" / "bluetooth"
        for pasta in (self.dev_input, self.sys_hidraw, self.sys_input):
            pasta.mkdir(parents=True, exist_ok=True)
        (self.bluetooth / "hci0").mkdir(parents=True)
        (self.bluetooth / "hci0" / "address").write_text(
            MAC_DO_ADAPTADOR + "\n", encoding="ascii"
        )
        self._seq = 0x06
        self.aparelhos: dict[str, Aparelho] = {}

    def no(self, base: str) -> str:
        return str(self.dev / base)

    def nascer(self, base: str, tipo: str, n: int, *, aberto: bool = False) -> Aparelho:
        """Um aparelho novo atrás do nome `base`, com o `<seq>` seguinte.

        `tipo`: `radio` (DualSense físico pelo BT, sob o `uhid` do BlueZ),
        `cabo` (DualSense físico pelo USB real), `edge` (o Edge pelo cabo),
        `pad` (o nosso pad `uhid` do modo DualSense) ou `teclado` (um HID
        qualquer pelo rádio). O físico nasce `0600` sem ACL (a regra da cura)
        salvo `aberto`; o pad e o teclado nascem abertos para ela.
        """
        seq = self._seq
        self._seq += 1
        uhid = self.raiz / "sys" / "devices" / "virtual" / "misc" / "uhid"
        usb = self.raiz / "sys" / "devices" / "pci0000:00" / "usb1" / f"1-{n}" / f"1-{n}:1.3"
        if tipo == "radio":
            bus, vendor, produto, topo = "0005", "054C", "0CE6", uhid
            extra = f"HID_PHYS={MAC_DO_ADAPTADOR}\nHID_UNIQ=e8:47:3a:00:00:{n:02x}\n"
        elif tipo == "cabo":
            bus, vendor, produto, topo, extra = "0003", "054C", "0CE6", usb, ""
        elif tipo == "edge":
            bus, vendor, produto, topo, extra = "0003", "054C", "0DF2", usb, ""
        elif tipo == "pad":
            bus, vendor, produto, topo = "0003", "054C", "0DF2", uhid
            extra = f"HID_PHYS=hefesto-vpad-p{n}\nHID_UNIQ=02:fe:00:00:00:{n:02x}\n"
        elif tipo == "teclado":
            bus, vendor, produto, topo = "0005", "3554", "FA09", uhid
            extra = f"HID_PHYS={MAC_DO_ADAPTADOR}\nHID_UNIQ=e8:47:3a:00:01:{n:02x}\n"
        else:  # pragma: no cover - erro de quem escreve o teste
            raise ValueError(tipo)
        hid = f"{bus}:{vendor}:{produto}.{seq:04X}"
        hid_dir = topo / hid
        hid_dir.mkdir(parents=True)
        (hid_dir / "uevent").write_text(
            f"DRIVER=x\nHID_ID={bus}:0000{vendor}:0000{produto}\nHID_NAME=x\n{extra}",
            encoding="ascii",
        )
        classe = self.sys_hidraw / base
        classe.mkdir()
        (classe / "dev").write_text("0:0\n", encoding="ascii")
        (classe / "device").symlink_to(hid_dir)
        do_jogo = tipo in ("pad", "teclado")
        self._criar_no(self.dev / base, aberto=aberto or do_jogo)
        inputs: list[tuple[str, tuple[str, ...]]]
        if tipo == "teclado":
            inputs = [("Teclado", (f"event{seq}0",))]
        else:
            nome = "DualSense Wireless Controller"
            if tipo == "pad":
                nome = f"{nome} (Hefesto P{n})"
            inputs = [
                (nome, (f"event{seq}0", f"js{seq}0")),
                (f"{nome} Motion Sensors", (f"event{seq}1", f"js{seq}1")),
                (f"{nome} Touchpad", (f"event{seq}2",)),
                (f"{nome} Headset Jack", (f"event{seq}3",)),
            ]
        entradas: list[Path] = []
        for i, (nome_do_input, filhos) in enumerate(inputs):
            d = hid_dir / "input" / f"input{seq}{i}"
            d.mkdir(parents=True)
            (d / "name").write_text(nome_do_input + "\n", encoding="utf-8")
            for filho in filhos:
                (d / filho).mkdir()
                (d / filho / "dev").write_text("0:0\n", encoding="ascii")
                (self.sys_input / filho).symlink_to(d / filho)
                no = self.dev_input / filho
                self._criar_no(no, aberto=aberto or do_jogo)
                entradas.append(no)
        aparelho = Aparelho(base, hid, hid_dir, entradas)
        self.aparelhos[base] = aparelho
        return aparelho

    @staticmethod
    def _criar_no(caminho: Path, *, aberto: bool) -> None:
        caminho.write_text("", encoding="ascii")
        if aberto:
            caminho.chmod(0o660)
            os.setxattr(caminho, ACL, encode_access_acl(UID))
        else:
            caminho.chmod(0o600)

    def sair(self, base: str) -> None:
        """O aparelho sai: o kernel apaga o nome, o pai HID e os nós dele."""
        aparelho = self.aparelhos.pop(base)
        shutil.rmtree(self.sys_hidraw / base)
        (self.dev / base).unlink()
        for no in aparelho.entradas:
            (self.sys_input / no.name).unlink()
            no.unlink()
        shutil.rmtree(aparelho.hid_dir)

    def trocar(self, base: str, tipo: str, n: int, *, aberto: bool = False) -> Aparelho:
        """O aparelho de `base` sai e outro nasce com o MESMO nome e o mesmo `dev`."""
        self.sair(base)
        return self.nascer(base, tipo, n, aberto=aberto)

    def emudecer(self, base: str) -> None:
        """O diretório do nome existe, e a leitura do `device` falha."""
        enlace = self.sys_hidraw / base / "device"
        enlace.unlink()
        enlace.write_text("", encoding="ascii")

    def ops(self) -> _Gravador:
        return _Gravador(
            sys_class_hidraw=str(self.sys_hidraw),
            dev_input_root=str(self.dev_input),
            sys_class_input=str(self.sys_input),
            sys_class_bluetooth=str(self.bluetooth),
        )


class _StatQueAceitaArquivo(ModuleType):
    """O módulo `stat` com UMA troca: o `S_ISCHR` aceita arquivo comum.

    Só o `hidraw_broker` o recebe, e só enquanto o teste vive (o molde da
    `test_o_broker_nao_reescreve_o_que_nao_mudou.py`).
    """

    def __init__(self) -> None:
        super().__init__("stat")

    def __getattr__(self, nome: str) -> Any:
        return getattr(stat, nome)

    @staticmethod
    def S_ISCHR(modo: int) -> bool:  # noqa: N802 - espelha o nome do stdlib
        return stat.S_ISCHR(modo) or stat.S_ISREG(modo)


class _Gravador(FsAclOps):
    """O `FsAclOps` de produção, anotando cada pedido de escrita.

    Anota antes de delegar: o que importa à régua 5 é se o broker PEDIU ao fs,
    e não se o `_pin` recusou depois.
    """

    _e_char_device = staticmethod(stat.S_ISREG)

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.chamadas: list[tuple[str, str]] = []

    def hide(self, node: str, base: str) -> None:
        self.chamadas.append(("hide", base))
        super().hide(node, base)

    def restore(self, node: str, base: str, uid: int) -> None:
        self.chamadas.append(("restore", base))
        super().restore(node, base, uid)

    def fechar_entradas(self, base: str) -> tuple[list[str], list[str]]:
        self.chamadas.append(("fechar_entradas", base))
        return super().fechar_entradas(base)

    def abrir_entradas(self, base: str, uid: int) -> tuple[list[str], list[str]]:
        self.chamadas.append(("abrir_entradas", base))
        return super().abrir_entradas(base, uid)


@pytest.fixture
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mesa:
    sonda = tmp_path / "sonda-de-acl"
    sonda.write_text("", encoding="ascii")
    try:
        os.setxattr(sonda, ACL, encode_access_acl(UID))
    except OSError as exc:  # pragma: no cover - depende do fs do CI
        pytest.skip(f"o fs de teste não guarda ACL POSIX: {exc}")
    finally:
        sonda.unlink()
    monkeypatch.setattr(hb, "stat_mod", _StatQueAceitaArquivo())
    return Mesa(tmp_path)


Diario = list[tuple[str, dict[str, Any]]]


def _estado(
    mesa: Mesa, *, ops: Any | None = None, no_nasce_fechado: bool = True
) -> tuple[BrokerState, Any, Diario]:
    """O `BrokerState` de produção, com o validador e o `FsAclOps` de produção."""
    diario: Diario = []
    ops = mesa.ops() if ops is None else ops
    st = BrokerState(
        allowed_uid=UID,
        ops=ops,
        dev_root=str(mesa.dev),
        sys_class_hidraw=str(mesa.sys_hidraw),
        sys_class_bluetooth=str(mesa.bluetooth),
        dev_input_root=str(mesa.dev_input),
        sys_class_input=str(mesa.sys_input),
        log=lambda evento, **campos: diario.append((evento, campos)),
        sleep_fn=lambda _s: None,
        no_nasce_fechado=no_nasce_fechado,
    )
    return st, ops, diario


def _pede(st: BrokerState, conn: int, payload: dict[str, Any]) -> dict[str, Any]:
    resposta, fd = st.handle_line(conn, UID, json.dumps(payload).encode())
    if fd is not None:
        os.close(fd)
    return dict(resposta)


def _escondidos(st: BrokerState) -> list[str]:
    return list(_pede(st, DAEMON, {"cmd": "status"})["hidden"])


def _podas(diario: Diario) -> list[dict[str, Any]]:
    return [campos for evento, campos in diario if evento == EVENTO]


def _retrato(caminho: Path) -> tuple[int, bytes | None]:
    """O modo e a ACL crua do nó, como estão no fs."""
    modo = stat.S_IMODE(caminho.stat().st_mode)
    try:
        acl: bytes | None = os.getxattr(caminho, ACL)
    except OSError:
        acl = None
    return modo, acl


def _a_cena_de_2909(mesa: Mesa) -> tuple[BrokerState, _Gravador, Diario, Aparelho]:
    """Os cinco escondidos pelo daemon; o vermelho sai e o pad do P2 herda o nome."""
    for i, base in enumerate(OS_QUATRO, start=2):
        mesa.nascer(base, "radio", i)
    vermelho = mesa.nascer(O_DO_P1, "radio", 1)
    st, ops, diario = _estado(mesa)
    for base in (*OS_QUATRO, O_DO_P1):
        assert _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(base)})["state"] == "hidden"
    assert len(_escondidos(st)) == 5
    mesa.trocar(O_DO_P1, "pad", 2)
    return st, ops, diario, vermelho


# ---------------------------------------------------------------------------
# 1. A cena de 29/09
# ---------------------------------------------------------------------------


class TestACenaDe2909:
    def test_o_status_devolve_os_quatro_e_o_diario_diz_quem_saiu(self, mesa: Mesa) -> None:
        """MORDIDA: tire a chamada da poda do `handle_line`, e o `status` volta
        a ter cinco. MORDIDA 2: compare o `dev` do sysfs em vez do pai HID; ele
        é `0:0` antes e depois, e o `status` volta a ter cinco."""
        st, _ops, diario, vermelho = _a_cena_de_2909(mesa)

        assert _escondidos(st) == sorted(mesa.no(b) for b in OS_QUATRO)
        pad = mesa.aparelhos[O_DO_P1]
        assert _podas(diario) == [
            {"node": mesa.no(O_DO_P1), "de": vermelho.hid, "agora": pad.hid}
        ]
        assert mesa.no(O_DO_P1) not in st.by_conn.get(DAEMON, set())

    def test_a_mordida_sem_a_poda_o_status_volta_a_ter_cinco(
        self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(BrokerState, "_podar_o_que_saiu", lambda self, **_kw: None)
        st, _ops, diario, _vermelho = _a_cena_de_2909(mesa)
        assert mesa.no(O_DO_P1) in _escondidos(st)
        assert _podas(diario) == []

    @pytest.mark.parametrize("herdeiro", ["pad", "teclado", "ninguem"])
    @pytest.mark.parametrize(
        ("jogador", "base", "tipo"),
        [
            ("P1", "hidraw3", "radio"),
            ("P2", "hidraw5", "radio"),
            ("P3", "hidraw7", "cabo"),
            ("P4", "hidraw9", "edge"),
        ],
    )
    def test_qualquer_jogador_em_qualquer_transporte(
        self, mesa: Mesa, jogador: str, base: str, tipo: str, herdeiro: str
    ) -> None:
        """A poda não sabe de jogador, de transporte nem de modo.

        O herdeiro do nome é o pad do modo DualSense, um teclado (o nome vai a
        qualquer aparelho no modo Xbox, cujo pad `uinput` não tem hidraw) ou
        ninguém (o cabo tirado).
        """
        mesa_de_quatro = (
            ("hidraw3", "radio", 1),
            ("hidraw5", "radio", 2),
            ("hidraw7", "cabo", 3),
            ("hidraw9", "edge", 4),
        )
        for b, t, n in mesa_de_quatro:
            mesa.nascer(b, t, n)
        st, _ops, diario = _estado(mesa)
        for b, _t, _n in mesa_de_quatro:
            assert _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(b)})["state"] == "hidden"

        if herdeiro == "ninguem":
            mesa.sair(base)
        else:
            mesa.trocar(base, herdeiro, int(jogador[1]))

        esperados = sorted(mesa.no(b) for b, _t, _n in mesa_de_quatro if b != base)
        assert _escondidos(st) == esperados, (jogador, tipo, herdeiro)
        podas = _podas(diario)
        assert [p["node"] for p in podas] == [mesa.no(base)]
        assert podas[0]["agora"] == ("-" if herdeiro == "ninguem" else mesa.aparelhos[base].hid)


# ---------------------------------------------------------------------------
# 2. O nome some
# ---------------------------------------------------------------------------


class TestONomeSome:
    def test_o_nome_sem_diretorio_sai_do_status(self, mesa: Mesa) -> None:
        """MORDIDA: faça o `pai_hid_do_no` devolver `None` para o diretório
        ausente (sumido lido como mudo), e a entrada fica."""
        vermelho = mesa.nascer(O_DO_P1, "radio", 1)
        st, _ops, diario = _estado(mesa)
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})
        mesa.sair(O_DO_P1)

        assert _escondidos(st) == []
        assert _podas(diario) == [{"node": mesa.no(O_DO_P1), "de": vermelho.hid, "agora": "-"}]

    @pytest.mark.parametrize("no_nasce_fechado", [True, False], ids=["cura", "mundo-antigo"])
    def test_o_eof_nao_pede_nada_ao_fs_pelo_nome_que_sumiu(
        self, mesa: Mesa, no_nasce_fechado: bool
    ) -> None:
        """A poda roda também no EOF: sem ela, o `_repouso` pedia `hide` (ou
        `restore`, no mundo histórico) e `fechar_entradas` por um nome que já
        não é de ninguém. MORDIDA: tire a poda do `on_conn_closed`, e o
        gravador anota o `hidraw6`."""
        mesa.nascer("hidraw5", "radio", 2)
        mesa.nascer(O_DO_P1, "radio", 1)
        st, ops, _diario = _estado(mesa, no_nasce_fechado=no_nasce_fechado)
        for base in ("hidraw5", O_DO_P1):
            _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(base)})
        mesa.sair(O_DO_P1)
        ops.chamadas.clear()

        restaurados = st.on_conn_closed(DAEMON)

        assert [c for c in ops.chamadas if c[1] == O_DO_P1] == []
        assert restaurados == [mesa.no("hidraw5")]
        assert st.hidden == {}


# ---------------------------------------------------------------------------
# 3. O mesmo controle volta com o mesmo nome e outro <seq>
# ---------------------------------------------------------------------------


class TestOMesmoControleVolta:
    def test_a_lease_velha_sai_e_a_nova_lembra_o_pai_novo(self, mesa: Mesa) -> None:
        """O vermelho às 02:49:21: saiu e voltou com o mesmo nome.

        MORDIDA: rode a poda DEPOIS do `cmd`. O `hide` acha o nome já no
        `held` da conexão e não grava o pai novo; a poda de depois o tira, e o
        `status` sai sem o nome que acabou de ser escondido.
        """
        antes = mesa.nascer(O_DO_P1, "radio", 1)
        st, _ops, diario = _estado(mesa)
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})
        depois = mesa.trocar(O_DO_P1, "radio", 1, aberto=True)

        resposta = _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})

        assert resposta["state"] == "hidden"
        assert _retrato(mesa.dev / O_DO_P1) == (0o600, None)
        for no in depois.entradas:
            if not no.name.startswith("js") or not no.name.endswith("1"):
                assert _retrato(no) == (0o600, None), no.name
        assert _escondidos(st) == [mesa.no(O_DO_P1)]
        assert _podas(diario) == [
            {"node": mesa.no(O_DO_P1), "de": antes.hid, "agora": depois.hid}
        ]
        assert _escondidos(st) == [mesa.no(O_DO_P1)], "a lease nova não pode cair"


# ---------------------------------------------------------------------------
# 4. Nada muda, nada sai
# ---------------------------------------------------------------------------


class TestNadaMudaNadaSai:
    def test_duas_leases_do_mesmo_aparelho_seguem_contadas(self, mesa: Mesa) -> None:
        """MORDIDA: trate todo pai como mudado (a poda que esquece tudo), e o
        nome sai do `status` com as duas leases vivas."""
        mesa.nascer("hidraw5", "radio", 2)
        st, _ops, diario = _estado(mesa)
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no("hidraw5")})
        _pede(st, OUTRA, {"cmd": "hide", "node": mesa.no("hidraw5")})

        assert _escondidos(st) == [mesa.no("hidraw5")]
        assert st.hidden[mesa.no("hidraw5")].refcount == 2

        resposta = _pede(st, OUTRA, {"cmd": "restore", "node": mesa.no("hidraw5")})

        assert resposta["state"] == "hidden"
        assert _retrato(mesa.dev / "hidraw5") == (0o600, None)
        assert _escondidos(st) == [mesa.no("hidraw5")]
        assert _podas(diario) == []


# ---------------------------------------------------------------------------
# 5. A poda não escreve
# ---------------------------------------------------------------------------


class TestAPodaNaoEscreve:
    def test_a_poda_do_nome_herdado_pelo_pad_nao_pede_nada_ao_fs(self, mesa: Mesa) -> None:
        """O pad é o controle que o jogo vê: nada nele muda.

        MORDIDA: solte a lease podada pelo `_repouso` (o jeito do `restore`), e
        o gravador anota o `hide` do `_fs_fechar`, mesmo com o `_pin` recusando
        o pad depois. O modo do arquivo sozinho não morde, porque o `_pin` já o
        protege; quem morde é o gravador.
        """
        mesa.nascer(O_DO_P1, "radio", 1)
        st, ops, diario = _estado(mesa)
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})
        pad = mesa.trocar(O_DO_P1, "pad", 2)
        antes = {no: _retrato(no) for no in (mesa.dev / O_DO_P1, *pad.entradas)}
        ops.chamadas.clear()

        assert _escondidos(st) == []

        assert ops.chamadas == []
        assert len(_podas(diario)) == 1
        assert {no: _retrato(no) for no in antes} == antes
        assert antes[mesa.dev / O_DO_P1] == (0o660, encode_access_acl(UID))


# ---------------------------------------------------------------------------
# 6. A exposição e os nós de entrada seguem
# ---------------------------------------------------------------------------


class TestAExposicaoSegue:
    def test_o_hide_do_fisico_novo_com_o_nome_nao_e_adiado(self, mesa: Mesa) -> None:
        """O Modo Nativo expôs um físico que saiu; outro físico chega com o nome.

        MORDIDA: pode só o `hidden`, e o `hide` volta `state: "exposed"`
        (`hide_adiado_por_exposicao`) com o nome no `entradas_expostas`.
        """
        mesa.nascer(O_DO_P1, "radio", 1)
        st, _ops, diario = _estado(mesa)
        exposto = _pede(st, NATIVO, {"cmd": "expose", "node": mesa.no(O_DO_P1), "entradas": True})
        assert exposto["state"] == "exposed"
        mesa.trocar(O_DO_P1, "radio", 5)

        resposta = _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})
        status = _pede(st, DAEMON, {"cmd": "status"})

        assert resposta["state"] == "hidden"
        assert status["entradas_expostas"] == []
        assert status["expostos"] == []
        assert status["hidden"] == [mesa.no(O_DO_P1)]
        assert not any(evento == "hide_adiado_por_exposicao" for evento, _ in diario)
        assert mesa.no(O_DO_P1) not in st.expostos_by_conn.get(NATIVO, set())


# ---------------------------------------------------------------------------
# 7. Sysfs mudo não poda
# ---------------------------------------------------------------------------


class _Mudavel(_Gravador):
    """O `pai_hid_do_no` de produção, que emudece quando a régua manda."""

    mudo = False

    def pai_hid_do_no(self, base: str) -> str | None:
        if self.mudo:
            return None
        return super().pai_hid_do_no(base)


class TestSysfsMudoNaoPoda:
    def test_o_device_ilegivel_agora_nao_poda(self, mesa: Mesa) -> None:
        """MORDIDA: trate `None` como «mudou», e a lease cai."""
        mesa.nascer(O_DO_P1, "radio", 1)
        st, _ops, diario = _estado(mesa)
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})
        mesa.emudecer(O_DO_P1)

        assert _escondidos(st) == [mesa.no(O_DO_P1)]
        assert _podas(diario) == []

    def test_mudo_agora_mesmo_com_o_aparelho_trocado(self, mesa: Mesa) -> None:
        mesa.nascer(O_DO_P1, "radio", 1)
        st, ops, diario = _estado(mesa, ops=_Mudavel(
            sys_class_hidraw=str(mesa.sys_hidraw),
            dev_input_root=str(mesa.dev_input),
            sys_class_input=str(mesa.sys_input),
            sys_class_bluetooth=str(mesa.bluetooth),
        ))
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})
        mesa.trocar(O_DO_P1, "pad", 2)
        ops.mudo = True

        assert _escondidos(st) == [mesa.no(O_DO_P1)]
        assert _podas(diario) == []

    def test_mudo_no_pedido_nao_sabe_o_aparelho_e_fica(self, mesa: Mesa) -> None:
        """O pai guardado `None` quer dizer «não sei qual aparelho ela escondeu»."""
        mesa.nascer(O_DO_P1, "radio", 1)
        ops = _Mudavel(
            sys_class_hidraw=str(mesa.sys_hidraw),
            dev_input_root=str(mesa.dev_input),
            sys_class_input=str(mesa.sys_input),
            sys_class_bluetooth=str(mesa.bluetooth),
        )
        st, _ops, diario = _estado(mesa, ops=ops)
        ops.mudo = True
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no(O_DO_P1)})
        ops.mudo = False
        mesa.trocar(O_DO_P1, "pad", 2)

        assert _escondidos(st) == [mesa.no(O_DO_P1)]
        assert _podas(diario) == []


# ---------------------------------------------------------------------------
# 8. O dono da pergunta
# ---------------------------------------------------------------------------


class TestODonoDaPergunta:
    def test_o_broker_de_producao_sabe_perguntar(self) -> None:
        """Régua de dono, e não da palavra: sem ela, um dublê sem a pergunta
        esconderia a poda da produção. MORDIDA: renomeie o método no
        `FsAclOps`; esta reprova junto com a 1."""
        st = BrokerState(allowed_uid=UID)
        assert isinstance(st._ops, FsAclOps)
        assert callable(getattr(st._ops, "pai_hid_do_no", None))

    def test_as_tres_respostas(self, mesa: Mesa) -> None:
        """O pai HID quando o `device` resolve; `""` (sumido) sem o diretório
        do nome; `None` (mudo) com o diretório e a leitura falhando."""
        aparelho = mesa.nascer("hidraw5", "radio", 2)
        ops = FsAclOps(sys_class_hidraw=str(mesa.sys_hidraw))

        assert ops.pai_hid_do_no("hidraw5") == os.path.realpath(aparelho.hid_dir)
        assert ops.pai_hid_do_no("hidraw99") == ""
        mesa.emudecer("hidraw5")
        assert ops.pai_hid_do_no("hidraw5") is None

    def test_a_mordida_sem_a_pergunta_a_cena_volta_a_ter_cinco(
        self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delattr(FsAclOps, "pai_hid_do_no")
        st, _ops, _diario, _vermelho = _a_cena_de_2909(mesa)
        assert len(_escondidos(st)) == 5


# ---------------------------------------------------------------------------
# 9. O caminho que já funcionava: o restore do secundário que saiu
# ---------------------------------------------------------------------------


class TestOCaminhoQueJaFuncionava:
    @pytest.mark.parametrize("herdeiro", ["ninguem", "pad"])
    def test_o_restore_do_dono_responde_gone_e_a_poda_nao_fala(
        self, mesa: Mesa, herdeiro: str
    ) -> None:
        """O `_teardown_player` do co-op pede o `restore` do nome do secundário
        que saiu (02:17:45, `restored … state=gone`). O pedido explícito do
        dono sobre o próprio nome vence a poda: a resposta segue a de sempre, e
        o diário não ganha a linha da poda. MORDIDA: tire a exceção do pedido
        que solta o próprio nome, e a resposta vira
        `reject_not_physical_dualsense`."""
        mesa.nascer("hidraw7", "cabo", 3)
        st, _ops, diario = _estado(mesa)
        _pede(st, DAEMON, {"cmd": "hide", "node": mesa.no("hidraw7")})
        if herdeiro == "ninguem":
            mesa.sair("hidraw7")
        else:
            mesa.trocar("hidraw7", "pad", 3)

        resposta = _pede(st, DAEMON, {"cmd": "restore", "node": mesa.no("hidraw7")})

        assert resposta == {
            "ok": True, "cmd": "restore", "node": mesa.no("hidraw7"), "state": "gone",
        }
        assert _podas(diario) == []
        assert _escondidos(st) == []
