"""DESLIGAR-COM-A-STEAM-ABERTA-DEVOLVE-O-CONTROLE-A-ELA-01 — a entrega religa o driver HID.

A bancada de 23/10/2026 (rodadas A8 a A11): com a Steam aberta ANTES de desligar
o Hefesto, a entrega do broker (só a ACL e o modo do nó) não a faz abrir o
DualSense de novo: ela enumerou o físico com o nó fechado (``0600 root``, a
regra 73) e não volta a um aparelho que já conhece, nem com a ACL nova nem com
um evento sintético do udev. Só o nó que NASCE de novo volta à lista dela, e
quem o recria é soltar e prender o driver HID (``unbind``/``bind`` com o id do
pai HID do ``hidraw``).

A cura, no broker: na transição da PRIMEIRA entrega (e só nela), ele solta e
prende o driver de cada DualSense físico entregue. A mesa é a do arquivo
vizinho (``/sys`` e ``/dev`` de mentira em ``tmp_path``, o ``BrokerState`` e o
``FsAclOps`` de produção); aqui ganha o ``driver`` de cada pai HID e o diretório
dos drivers, e nunca o aparelho.

Cada régua diz a sua MORDIDA.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import Broker, BrokerState
from tests.unit.test_desligar_o_hefesto_devolve_o_controle_ao_linux import (
    GRACA,
    Cena,
    Relogio,
    _aberto_para_a_sessao,
    _fechado,
    _tudo_do_aparelho,
)
from tests.unit.test_o_broker_esquece_o_controle_que_saiu import (
    UID,
    Mesa,
    _estado,
    _Gravador,
)
from tests.unit.test_o_broker_esquece_o_controle_que_saiu import mesa as mesa

REPO = Path(__file__).resolve().parents[2]
UNIT = REPO / "assets" / "systemd" / "hefesto-hidraw-broker.service"

DRIVER = "playstation"


class Religador(_Gravador):
    """O ``FsAclOps`` de produção anotando cada pedido de ``unbind``/``bind``.

    A escrita é a de produção (``_escrever_attr`` num arquivo do ``tmp_path``);
    ``falhar`` só faz o pedido levantar o ``OSError`` que o sysfs levantaria,
    N vezes, antes de escrever.
    """

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.escritas: list[tuple[str, str]] = []
        self.falhar: dict[str, int] = {}
        self.link_some = False

    def aparelho_e_driver_hid(self, base: str) -> tuple[str, str] | None:
        if self.link_some:
            raise OSError(errno.ENOENT, "o link sumiu")
        return super().aparelho_e_driver_hid(base)

    def _anota(self, passo: str, aparelho: str) -> None:
        self.escritas.append((passo, aparelho))
        if self.falhar.get(passo, 0) > 0:
            self.falhar[passo] -= 1
            raise OSError(errno.EBUSY, f"{passo} recusado")

    def soltar_driver_hid(self, aparelho: str, driver: str) -> None:
        self._anota("unbind", aparelho)
        super().soltar_driver_hid(aparelho, driver)

    def prender_driver_hid(self, aparelho: str, driver: str) -> None:
        self._anota("bind", aparelho)
        super().prender_driver_hid(aparelho, driver)


class Renascedor(Religador):
    """O ``Religador`` com o kernel de verdade atrás: o ``unbind`` apaga o
    ``hidraw`` e os nós de entrada do aparelho, e o ``bind`` os recria FECHADOS
    (``0600 root``, a regra 73), com nós de entrada novos. Na mesa o id do pai
    HID avança com o ``<seq>``; no kernel ele fica, e a varredura não depende dele.
    """

    def __init__(self, mesa: Mesa, tipos: dict[str, tuple[str, int]], **kw: Any) -> None:
        super().__init__(**kw)
        self._mesa = mesa
        self._tipos = tipos
        self._soltos: dict[str, str] = {}
        self.renascidos: list[str] = []

    def soltar_driver_hid(self, aparelho: str, driver: str) -> None:
        super().soltar_driver_hid(aparelho, driver)
        base = next(b for b, a in self._mesa.aparelhos.items() if a.hid == aparelho)
        self._mesa.sair(base)
        self._soltos[aparelho] = base

    def prender_driver_hid(self, aparelho: str, driver: str) -> None:
        super().prender_driver_hid(aparelho, driver)
        base = self._soltos.pop(aparelho)
        tipo, n = self._tipos[base]
        self._mesa.nascer(base, tipo, n)
        _com_driver(self._mesa, base, driver)
        assert all(_fechado(no) for no in _tudo_do_aparelho(self._mesa, base)), base
        self.renascidos.append(base)


class _OpsAntigo(_Gravador):
    """Um ``ops`` de antes da cura: sabe a ACL, não sabe religar."""

    aparelho_e_driver_hid = None  # type: ignore[assignment]
    soltar_driver_hid = None  # type: ignore[assignment]
    prender_driver_hid = None  # type: ignore[assignment]


def _com_driver(mesa: Mesa, base: str, driver: str = DRIVER) -> str:
    """Prende o ``driver`` ao pai HID de ``base`` (o link ``device/driver``) e
    devolve o id do aparelho. O diretório dos drivers ganha ``bind``/``unbind``
    vazios, como o kernel os publica."""
    raiz = mesa.raiz / "sys" / "bus" / "hid" / "drivers" / driver
    raiz.mkdir(parents=True, exist_ok=True)
    for atributo in ("bind", "unbind"):
        (raiz / atributo).write_text("", encoding="ascii")
    aparelho = mesa.aparelhos[base]
    (aparelho.hid_dir / "driver").symlink_to(raiz)
    return aparelho.hid


def _drivers(mesa: Mesa) -> Path:
    return mesa.raiz / "sys" / "bus" / "hid" / "drivers"


def _raizes(mesa: Mesa) -> dict[str, str]:
    return {
        "sys_class_hidraw": str(mesa.sys_hidraw),
        "dev_input_root": str(mesa.dev_input),
        "sys_class_input": str(mesa.sys_input),
        "sys_class_bluetooth": str(mesa.bluetooth),
        "sys_bus_hid_drivers": str(_drivers(mesa)),
    }


def _ops(mesa: Mesa) -> Religador:
    return Religador(**_raizes(mesa))


class CenaReligavel(Cena):
    """A cena do arquivo vizinho com o ``Religador`` no lugar do ``FsAclOps``."""

    def __init__(self, mesa: Mesa, ops: Religador | None = None) -> None:
        self.mesa = mesa
        self.relogio = Relogio()
        self.st, self.ops, self.diario = _estado(
            mesa, ops=_ops(mesa) if ops is None else ops, no_nasce_fechado=True
        )
        self.broker = Broker(
            self.st,
            None,
            peercred_fn=lambda _s: (4242, UID, UID),
            log=lambda *_a, **_k: None,
            graca_da_entrega_s=GRACA,
            relogio=self.relogio,
        )
        self._pontas = {}

    def para_o_daemon(self, bases: list[str]) -> None:
        conn = self.conectar()
        self.o_daemon_esconde(conn, bases)
        self.desconectar(conn)


@pytest.fixture
def cena(mesa: Mesa) -> CenaReligavel:
    """Um físico no rádio (hidraw5), o pad do Hefesto (hidraw6), um externo
    (hidraw7) e um físico no cabo (hidraw9). TODOS têm driver HID preso: é o
    validador, e não a falta de driver, que tira o pad e o externo da conta."""
    mesa.nascer("hidraw5", "radio", 1)
    mesa.nascer("hidraw6", "pad", 2)
    mesa.nascer("hidraw7", "teclado", 3)
    mesa.nascer("hidraw9", "cabo", 4)
    for base in ("hidraw5", "hidraw6", "hidraw7", "hidraw9"):
        _com_driver(mesa, base)
    return CenaReligavel(mesa)


def _eventos(cena: CenaReligavel, nome: str) -> list[dict[str, Any]]:
    return [campos for evento, campos in cena.diario if evento == nome]


class TestAPrimeiraEntregaReligaODriver:
    def test_a_primeira_entrega_religa_o_driver_de_cada_fisico(
        self, cena: CenaReligavel
    ) -> None:
        """A prova de D-2310-DESLIGAR-COM-A-STEAM-ABERTA-RELIGA-O-DRIVER.

        MORDIDA: tire o ``_religar_o_driver_dos_fisicos`` da entrega, e a Steam
        aberta não acha o controle (A8, xinput 3)."""
        mesa = cena.mesa
        radio, cabo = mesa.aparelhos["hidraw5"].hid, mesa.aparelhos["hidraw9"].hid
        pad, externo = mesa.aparelhos["hidraw6"].hid, mesa.aparelhos["hidraw7"].hid
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        assert cena.ops.escritas == []

        cena.tique(GRACA)

        assert cena.st.entregue is True
        assert cena.ops.escritas == [
            ("unbind", radio), ("bind", radio),
            ("unbind", cabo), ("bind", cabo),
        ], "cada físico solta e prende, nesta ordem, e o pad e o externo ficam de fora"
        tocados = {id_ for _, id_ in cena.ops.escritas}
        assert pad not in tocados and externo not in tocados
        assert (_drivers(mesa) / DRIVER / "unbind").read_text(encoding="ascii") == cabo
        assert (_drivers(mesa) / DRIVER / "bind").read_text(encoding="ascii") == cabo
        for base in ("hidraw5", "hidraw9"):
            assert _aberto_para_a_sessao(mesa.dev / base), base
        assert [c["nodes"] for c in _eventos(cena, "driver_hid_religado")] == [
            f"{mesa.dev}/hidraw5,{mesa.dev}/hidraw9"
        ]

    def test_a_escrita_vai_ao_arquivo_do_driver_do_proprio_aparelho(self, mesa: Mesa) -> None:
        """Dois drivers: cada id vai ao ``unbind`` e ao ``bind`` do SEU driver."""
        mesa.nascer("hidraw5", "radio", 1)
        mesa.nascer("hidraw9", "cabo", 4)
        radio = _com_driver(mesa, "hidraw5", "playstation")
        cabo = _com_driver(mesa, "hidraw9", "hid-generic")
        cena = CenaReligavel(mesa)
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)
        for driver, id_ in (("playstation", radio), ("hid-generic", cabo)):
            for passo in ("unbind", "bind"):
                lido = (_drivers(mesa) / driver / passo).read_text(encoding="ascii")
                assert lido == id_, (driver, passo)

    def test_sem_driver_preso_nada_se_escreve_e_a_entrega_segue(self, mesa: Mesa) -> None:
        mesa.nascer("hidraw5", "radio", 1)
        cena = CenaReligavel(mesa)
        cena.para_o_daemon(["hidraw5"])
        cena.tique(GRACA)
        assert cena.ops.escritas == []
        assert cena.st.entregue is True
        assert _aberto_para_a_sessao(mesa.dev / "hidraw5")

    def test_o_ops_sem_o_religar_so_entrega(self, mesa: Mesa) -> None:
        """Um ``ops`` que não sabe religar (o dublê antigo) não derruba a entrega."""
        mesa.nascer("hidraw5", "radio", 1)
        _com_driver(mesa, "hidraw5")
        st, _, _diario = _estado(mesa, ops=_OpsAntigo(
            sys_class_hidraw=str(mesa.sys_hidraw),
            dev_input_root=str(mesa.dev_input),
            sys_class_input=str(mesa.sys_input),
            sys_class_bluetooth=str(mesa.bluetooth),
        ), no_nasce_fechado=True)
        assert st.entregar_ao_linux() == [str(mesa.dev / "hidraw5")]
        assert st.entregue is True

    def test_o_nome_de_driver_fora_da_forma_do_kernel_nao_vira_caminho(
        self, mesa: Mesa
    ) -> None:
        mesa.nascer("hidraw5", "radio", 1)
        aparelho = mesa.aparelhos["hidraw5"]
        (aparelho.hid_dir / "driver").symlink_to(mesa.raiz / "sys" / ".." / "..")
        assert _ops(mesa).aparelho_e_driver_hid("hidraw5") is None

    def test_o_pai_fora_da_forma_de_id_hid_nao_vira_escrita(self, mesa: Mesa) -> None:
        """O que vai ao ``unbind`` é só um id ``BUS:VVVV:PPPP.SEQ``."""
        mesa.nascer("hidraw5", "radio", 1)
        _com_driver(mesa, "hidraw5")
        estranho = mesa.raiz / "sys" / "devices" / "nao-e-hid"
        estranho.mkdir(parents=True)
        (estranho / "driver").symlink_to(_drivers(mesa) / DRIVER)
        enlace = mesa.sys_hidraw / "hidraw5" / "device"
        enlace.unlink()
        enlace.symlink_to(estranho)
        assert _ops(mesa).aparelho_e_driver_hid("hidraw5") is None

    def test_o_no_que_renasce_fechado_se_abre_na_varredura_seguinte(self, mesa: Mesa) -> None:
        """O ciclo inteiro, na forma do kernel: o ``bind`` recria o rádio e o cabo
        fechados, e a varredura do segundo seguinte os abre sem religar de novo.
        MORDIDA: religar em toda volta, e o nó renasce fechado a cada segundo."""
        tipos = {"hidraw5": ("radio", 1), "hidraw9": ("cabo", 4)}
        mesa.nascer("hidraw5", "radio", 1)
        mesa.nascer("hidraw6", "pad", 2)
        mesa.nascer("hidraw9", "cabo", 4)
        for base in ("hidraw5", "hidraw6", "hidraw9"):
            _com_driver(mesa, base)
        ops = Renascedor(mesa, tipos, **_raizes(mesa))
        cena = CenaReligavel(mesa, ops=ops)
        cena.para_o_daemon(["hidraw5", "hidraw9"])

        cena.tique(GRACA)
        feitas = list(ops.escritas)
        assert [p for p, _ in feitas] == ["unbind", "bind", "unbind", "bind"]
        assert ops.renascidos == ["hidraw5", "hidraw9"]

        cena.tique(1.0)
        for base in tipos:
            for no in _tudo_do_aparelho(mesa, base):
                assert _aberto_para_a_sessao(no), no
        assert _aberto_para_a_sessao(mesa.dev / "hidraw6"), "o pad segue como estava"
        cena.tique(1.0)
        assert ops.escritas == feitas


class TestSoNaPrimeiraEntrega:
    def test_a_varredura_de_cada_segundo_nao_religa(self, cena: CenaReligavel) -> None:
        """MORDIDA: religar em toda volta do laço (tire o ``if not self.entregue``
        em volta do religar), e o controle some do sistema a cada segundo."""
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)
        feitas = list(cena.ops.escritas)
        assert len(feitas) == 4

        for _ in range(3):
            cena.tique(1.0)
        assert cena.st.entregue is True
        assert cena.ops.escritas == feitas, "a varredura repetiu o unbind"

    def test_o_controle_que_conecta_depois_da_entrega_nao_e_religado(
        self, cena: CenaReligavel
    ) -> None:
        """Ele já nasce novo: a varredura o abre, e só."""
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)
        feitas = list(cena.ops.escritas)
        cena.mesa.nascer("hidraw11", "radio", 7)
        _com_driver(cena.mesa, "hidraw11")
        cena.tique(1.0)
        assert _aberto_para_a_sessao(cena.mesa.dev / "hidraw11")
        assert cena.ops.escritas == feitas

    def test_o_retorno_do_hefesto_nao_religa_nada(self, cena: CenaReligavel) -> None:
        """O ``retomar_o_esconderijo`` só fecha o nó; religar ali derrubaria o
        controle debaixo do Hefesto que acabou de voltar."""
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)
        feitas = list(cena.ops.escritas)
        volta = cena.conectar()
        cena.o_daemon_esconde(volta, ["hidraw5", "hidraw9"])
        assert cena.st.entregue is False
        assert cena.ops.escritas == feitas

    def test_desligar_de_novo_e_uma_primeira_entrega_nova(self, cena: CenaReligavel) -> None:
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)
        volta = cena.conectar()
        cena.o_daemon_esconde(volta, ["hidraw5", "hidraw9"])
        cena.desconectar(volta)
        cena.tique(GRACA)
        assert len(cena.ops.escritas) == 8


class TestAFalhaNaoDerrubaAEntrega:
    def test_o_bind_que_falha_tenta_de_novo_e_a_entrega_segue(
        self, cena: CenaReligavel
    ) -> None:
        """MORDIDA: tire a segunda tentativa do ``bind``, e o controle fica fora
        do sistema (sem ``bind`` o aparelho não tem driver)."""
        radio = cena.mesa.aparelhos["hidraw5"].hid
        cena.ops.falhar = {"bind": 1}
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)

        assert cena.ops.escritas[:3] == [("unbind", radio), ("bind", radio), ("bind", radio)]
        assert len(cena.ops.escritas) == 5
        assert _eventos(cena, "religar_falhou") == []
        assert cena.st.entregue is True
        assert _aberto_para_a_sessao(cena.mesa.dev / "hidraw5")

    def test_o_bind_que_falha_duas_vezes_e_logado_e_a_entrega_segue(
        self, cena: CenaReligavel
    ) -> None:
        cena.ops.falhar = {"bind": 2}
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)
        falhas = _eventos(cena, "religar_falhou")
        assert [(f["node"], f["passo"]) for f in falhas] == [
            (str(cena.mesa.dev / "hidraw5"), "bind")
        ]
        assert cena.ops.escritas[-2:] == [
            ("unbind", cena.mesa.aparelhos["hidraw9"].hid),
            ("bind", cena.mesa.aparelhos["hidraw9"].hid),
        ]
        for base in ("hidraw5", "hidraw9"):
            assert _aberto_para_a_sessao(cena.mesa.dev / base)

    def test_o_unbind_que_falha_e_logado_e_a_entrega_devolve_o_no_com_a_acl(
        self, cena: CenaReligavel
    ) -> None:
        """Sem ``unbind`` bom não há ``bind`` (o aparelho segue com o driver)."""
        cena.ops.falhar = {"unbind": 2}
        cena.para_o_daemon(["hidraw5", "hidraw9"])
        cena.tique(GRACA)
        assert [p for p, _ in cena.ops.escritas] == ["unbind", "unbind"]
        assert [f["passo"] for f in _eventos(cena, "religar_falhou")] == ["unbind", "unbind"]
        assert cena.st.entregue is True
        for base in ("hidraw5", "hidraw9"):
            assert _aberto_para_a_sessao(cena.mesa.dev / base), base
            for no in _tudo_do_aparelho(cena.mesa, base):
                assert _aberto_para_a_sessao(no)


class TestAUnit:
    @staticmethod
    def _diretivas(chave: str) -> list[str]:
        return [
            linha.split("=", 1)[1].strip()
            for linha in UNIT.read_text(encoding="utf-8").splitlines()
            if linha.startswith(f"{chave}=")
        ]

    def test_a_unit_deixa_escrever_no_driver_hid(self) -> None:
        """MORDIDA: tire ``-/sys/bus/hid/drivers`` do ``ReadWritePaths``, e o
        ``ProtectKernelTunables`` devolve EROFS ao ``unbind`` do broker."""
        gravaveis = " ".join(self._diretivas("ReadWritePaths")).split()
        assert sorted(gravaveis) == sorted([
            "-/sys/kernel/config",
            "-/sys/devices/platform",
            "-/run/hefesto-hidraw-broker",
            "-/sys/bus/hid/drivers",
        ])
        fonte = Path(hb.__file__).read_text(encoding="utf-8")
        assert 'SYS_BUS_HID_DRIVERS = "/sys/bus/hid/drivers"\n' in fonte

    def test_o_resto_do_endurecimento_fica_o_de_antes(self) -> None:
        for chave, esperado in {
            "ProtectSystem": ["strict"],
            "ProtectKernelTunables": ["yes"],
            "ProtectKernelModules": ["yes"],
            "ProtectHome": ["yes"],
            "NoNewPrivileges": ["yes"],
            "DevicePolicy": ["closed"],
            "DeviceAllow": ["char-hidraw rw", "char-input rw"],
            "CapabilityBoundingSet": [
                "CAP_FOWNER CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_SYS_PTRACE"],
        }.items():
            assert self._diretivas(chave) == esperado, chave


def test_o_estado_recebe_a_raiz_dos_drivers(mesa: Mesa, tmp_path: Path) -> None:
    """O ``BrokerState`` repassa a raiz ao ``FsAclOps`` que ele cria (a unit
    nunca precisa dela: o padrão é o ``/sys/bus/hid/drivers``)."""
    st = BrokerState(
        allowed_uid=os.getuid(),
        sys_class_hidraw=str(mesa.sys_hidraw),
        sys_bus_hid_drivers=str(tmp_path / "drivers"),
        log=lambda *_a, **_k: None,
    )
    assert st._ops._sys_bus_hid_drivers == str(tmp_path / "drivers")


def test_o_link_do_driver_que_some_no_meio_e_logado_e_a_entrega_segue(mesa: Mesa) -> None:
    """O aparelho sai entre a varredura e a leitura do link: o ``OSError`` do
    ``readlink`` vira ``religar_falhou`` (passo ``achar``), e a entrega fica."""
    mesa.nascer("hidraw5", "radio", 1)
    _com_driver(mesa, "hidraw5")
    cena = CenaReligavel(mesa)
    cena.ops.link_some = True
    cena.para_o_daemon(["hidraw5"])
    cena.tique(GRACA)
    assert cena.ops.escritas == []
    assert [f["passo"] for f in _eventos(cena, "religar_falhou")] == ["achar"]
    assert cena.st.entregue is True
    assert _aberto_para_a_sessao(mesa.dev / "hidraw5")
