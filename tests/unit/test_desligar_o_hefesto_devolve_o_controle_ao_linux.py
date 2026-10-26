"""DESLIGAR-O-HEFESTO-DEVOLVE-O-CONTROLE-AO-LINUX-01 — parar o Hefesto entrega o físico ao sistema.

A bancada de 03/10/2026: com o serviço parado, `/dev/hidraw5` ficava
`root:root 600`, sem ACL de usuário, e nenhum programa da sessão abria o
DualSense. A regra 73 faz o nó NASCER fechado, e o `_repouso` do broker o
devolvia a esse estado quando o último cliente saía: o fechado é o repouso de
quem tem Hefesto de pé. Quem para o serviço (aba Sistema, tray, `systemctl`)
espera o contrário.

A cura, no broker (a origem comum aos três gestos): sem NENHUMA conexão por
`GRACA_DA_ENTREGA_S`, ele entrega todo DualSense físico (e os nós de entrada
dele) à sessão, e o próximo pedido do Hefesto (`hide`/`expose`/`pad_usb_montar`)
fecha tudo de novo.

A MESA DE MENTIRA é a da `test_o_broker_esquece_o_controle_que_saiu.py`: o
`BrokerState`, o `Broker`, o `FsAclOps` e o validador são os de produção, sobre
um `/sys` e um `/dev` em `tmp_path`; o relógio é injetado e a conexão é um
`socketpair` de verdade (o EOF que fecha a lease é o do kernel).

Cada régua diz a sua MORDIDA.
"""
from __future__ import annotations

import json
import os
import socket
import stat
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import Broker, BrokerState
from tests.unit import test_o_broker_esquece_o_controle_que_saiu as _mesa_de_mentira
from tests.unit.test_o_broker_esquece_o_controle_que_saiu import (
    UID,
    Mesa,
    _estado,
    _retrato,
)

mesa = _mesa_de_mentira.mesa

GRACA = hb.GRACA_DA_ENTREGA_S

OS_SEIS = (
    ("hidraw5", "radio"),
    ("hidraw6", "radio"),
    ("hidraw7", "radio"),
    ("hidraw8", "radio"),
    ("hidraw9", "cabo"),
    ("hidraw10", "edge"),
)


class Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def passa(self, segundos: float) -> None:
        self.t += segundos


class Cena:
    """O broker de produção com o relógio na mão e uma conexão por vez."""

    def __init__(self, mesa: Mesa, *, no_nasce_fechado: bool = True,
                 graca: float = GRACA) -> None:
        self.mesa = mesa
        self.relogio = Relogio()
        self.st, self.ops, self.diario = _estado(mesa, no_nasce_fechado=no_nasce_fechado)
        self.broker = Broker(
            self.st,
            None,
            peercred_fn=lambda _s: (4242, UID, UID),
            log=lambda *_a, **_k: None,
            graca_da_entrega_s=graca,
            relogio=self.relogio,
        )
        self._pontas: dict[int, socket.socket] = {}

    def conectar(self) -> int:
        lado_broker, lado_cliente = socket.socketpair()
        conn = self.broker.register_client(lado_broker)
        assert conn is not None
        self._pontas[conn] = lado_cliente
        return conn

    def pedir(self, conn: int, payload: dict[str, Any]) -> dict[str, Any]:
        resposta, fd = self.st.handle_line(conn, UID, json.dumps(payload).encode())
        if fd is not None:
            os.close(fd)
        return dict(resposta)

    def desconectar(self, conn: int) -> None:
        """O cliente morre; o laço do broker vê o EOF, como em produção."""
        self._pontas.pop(conn).close()
        self.broker.step(timeout=0)

    def tique(self, segundos: float = 0.0) -> None:
        self.relogio.passa(segundos)
        self.broker.tique_da_entrega()

    def o_daemon_esconde(self, conn: int, bases: list[str]) -> None:
        """O que o daemon faz ao subir: expõe para abrir o handle, solta e esconde."""
        for base in bases:
            assert self.pedir(conn, {"cmd": "expose", "node": self.mesa.no(base)})["ok"]
            assert self.pedir(conn, {"cmd": "unexpose", "node": self.mesa.no(base)})["ok"]
            assert self.pedir(conn, {"cmd": "hide", "node": self.mesa.no(base)})["ok"]


def _modo(caminho: Path) -> int:
    return stat.S_IMODE(caminho.stat().st_mode)


def _aberto_para_a_sessao(caminho: Path) -> bool:
    modo, acl = _retrato(caminho)
    return modo == 0o660 and acl is not None and len(acl) > 28


def _fechado(caminho: Path) -> bool:
    modo, acl = _retrato(caminho)
    return modo == 0o600 and acl is None


def _tudo_do_aparelho(mesa: Mesa, base: str) -> list[Path]:
    """O hidraw e os nós de entrada que o broker trata (o `js` dos sensores de
    movimento fica de fora por desenho, `_SUFIXO_DO_MOVIMENTO`; na mesa ele é o
    `js` de índice 1)."""
    entradas = [
        n for n in mesa.aparelhos[base].entradas
        if not (n.name.startswith("js") and n.name.endswith("1"))
    ]
    return [mesa.dev / base, *entradas]


@pytest.fixture
def seis(mesa: Mesa) -> Cena:
    for n, (base, tipo) in enumerate(OS_SEIS, start=1):
        mesa.nascer(base, tipo, n)
    return Cena(mesa)


def _o_daemon_sobe_e_para(cena: Cena) -> int:
    """O daemon sobe, esconde os seis, e o serviço PARA: o EOF da lease."""
    conn = cena.conectar()
    cena.o_daemon_esconde(conn, [b for b, _ in OS_SEIS])
    for base, _ in OS_SEIS:
        assert all(_fechado(c) for c in _tudo_do_aparelho(cena.mesa, base)), base
    cena.desconectar(conn)
    return conn


class TestPararODaemonEntregaOFisico:
    def test_antes_da_graca_o_fisico_segue_fechado_e_depois_dela_e_da_sessao(
        self, seis: Cena
    ) -> None:
        """MORDIDA: tire a chamada de `tique_da_entrega` (ou o `entregar_ao_linux`
        dele) e os seis ficam `0600` para sempre, que é a bancada de 03/10.

        Prova da D-0810-PARAR-O-HEFESTO-DEVOLVE-O-FISICO.
        """
        _o_daemon_sobe_e_para(seis)

        seis.tique(GRACA - 1)
        for base, _ in OS_SEIS:
            assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, base)), (
                f"{base} abriu antes da graça: um reinício do daemon passaria por aqui")
        assert seis.st.entregue is False

        seis.tique(1.0)
        assert seis.st.entregue is True
        for base, tipo in OS_SEIS:
            for no in _tudo_do_aparelho(seis.mesa, base):
                assert _aberto_para_a_sessao(no), (
                    f"{tipo} {no.name}: a entrega não abriu o nó para a sessão")

    def test_os_nos_de_entrada_vao_junto_com_o_hidraw(self, seis: Cena) -> None:
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA)
        entradas = [n for b, _ in OS_SEIS for n in _tudo_do_aparelho(seis.mesa, b)[1:]]
        assert len(entradas) >= 6 * 4
        assert all(_aberto_para_a_sessao(n) for n in entradas)

    def test_o_reinicio_do_daemon_dentro_da_graca_nao_entrega_nada(self, seis: Cena) -> None:
        """O pior reinício medido (15 s) cabe na graça; entregar nele reabriria a
        janela da Steam que a regra 73 fecha."""
        _o_daemon_sobe_e_para(seis)
        seis.tique(15.0)
        volta = seis.conectar()
        seis.o_daemon_esconde(volta, [b for b, _ in OS_SEIS])
        seis.tique(GRACA * 3)
        assert seis.st.entregue is False
        for base, _ in OS_SEIS:
            assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, base))

    def test_o_controle_que_conecta_depois_da_entrega_tambem_e_entregue(
        self, seis: Cena
    ) -> None:
        """Hefesto parado, o P1 reconecta: o nó nasce fechado (regra 73) e a
        varredura do próximo segundo o abre. Sem a varredura, só os que já
        estavam ali seriam devolvidos."""
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA)
        seis.mesa.nascer("hidraw11", "radio", 7)
        assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, "hidraw11"))

        seis.tique(0.4)
        assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, "hidraw11")), (
            "a varredura rodou antes de passar um segundo: ela não pode custar "
            "uma volta do selector a cada pedido")
        seis.tique(0.7)
        assert all(_aberto_para_a_sessao(c) for c in _tudo_do_aparelho(seis.mesa, "hidraw11"))

    def test_o_pad_do_hefesto_e_os_externos_nao_sao_tocados(self, mesa: Mesa) -> None:
        """O validador só aceita DualSense físico: o pad (054c:0df2 sob o `uhid`) e
        um HID de outro fabricante (o externo) ficam exatamente como estavam."""
        mesa.nascer("hidraw5", "radio", 1)
        pad = mesa.nascer("hidraw6", "pad", 2)
        externo = mesa.nascer("hidraw7", "teclado", 3)
        cena = Cena(mesa)
        antes = {
            n: _retrato(n)
            for n in (mesa.dev / "hidraw6", mesa.dev / "hidraw7", *pad.entradas, *externo.entradas)
        }
        conn = cena.conectar()
        cena.o_daemon_esconde(conn, ["hidraw5"])
        cena.desconectar(conn)
        cena.tique(GRACA)

        assert _aberto_para_a_sessao(mesa.dev / "hidraw5")
        depois = {n: _retrato(n) for n in antes}
        assert depois == antes, "a entrega mexeu no que não é DualSense físico"

    def test_lease_orfa_de_restore_que_falhou_tambem_e_entregue(self, seis: Cena) -> None:
        """Um `restore` que falhou deixa o nó rastreado em `hidden` sem lease; a
        entrega é o restore que faltou, e não deixa lixo na contabilidade."""
        conn = seis.conectar()
        seis.o_daemon_esconde(conn, ["hidraw5"])
        seis.desconectar(conn)
        seis.st.hidden[seis.mesa.no("hidraw5")] = hb._HiddenNode(uid=UID, refcount=1)
        seis.tique(GRACA)
        assert seis.st.hidden == {} and seis.st.expostos == {}
        assert _aberto_para_a_sessao(seis.mesa.dev / "hidraw5")


class TestLigarDeNovoEscondeOutraVez:
    @pytest.mark.parametrize("pedido", ["hide", "expose"])
    def test_o_primeiro_pedido_do_hefesto_fecha_todo_o_fisico(
        self, seis: Cena, pedido: str
    ) -> None:
        """MORDIDA: tire o `retomar_o_esconderijo` do `handle_line` e o P2, que o
        daemon nem pediu, segue aberto para a Steam depois do «ligar»."""
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA)
        assert seis.st.entregue is True

        conn = seis.conectar()
        seis.tique(5.0)
        assert seis.st.entregue is True, "só conectar não é o Hefesto voltar"
        assert seis.pedir(conn, {"cmd": pedido, "node": seis.mesa.no("hidraw5")})["ok"]

        assert seis.st.entregue is False
        for base, _ in OS_SEIS[1:]:
            assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, base)), (
                f"{base} ficou aberto depois que o Hefesto voltou")

    def test_montar_o_pad_tambem_e_o_hefesto_voltando(self, seis: Cena) -> None:
        """O `pad_usb_montar` é pedido do daemon como o `hide`: fecha o físico
        antes de o pedido seguir. O pad de mentira recusa qualquer toque, e o
        serial inválido para o pedido antes do configfs. MORDIDA: tire o
        `pad_usb_montar` de `PEDIDOS_QUE_RETOMAM` e os seis seguem abertos."""

        class _PadIntocavel:
            def __getattr__(self, nome: str) -> Any:
                raise AssertionError(f"o pad de verdade foi tocado: {nome}")

        seis.st._pad_ops = _PadIntocavel()  # type: ignore[assignment]
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA)
        conn = seis.conectar()
        seis.pedir(conn, {"cmd": "pad_usb_montar", "serial": "x", "descritor": ""})
        assert seis.st.entregue is False
        for base, _ in OS_SEIS:
            assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, base)), base

    def test_o_controle_que_liga_com_um_cliente_conectado_nasce_fechado(
        self, seis: Cena
    ) -> None:
        """O daemon voltou e conectou, mas ainda não pediu `hide` nem `expose`
        (subiu sem controle à mão); o P1 liga agora. O nó nasce fechado pela
        regra 73 e a varredura da entrega NÃO pode abri-lo enquanto há cliente,
        ou a Steam o veria antes do `hide`. Quando o cliente sai sem pedir nada
        (era o exame da aba Conexões), a varredura volta no segundo seguinte.
        MORDIDA: tire a guarda de conexão viva do `tique_da_entrega` e o nó
        abre em um segundo, com o Hefesto de pé."""
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA)
        conn = seis.conectar()
        seis.mesa.nascer("hidraw11", "radio", 7)
        seis.tique(3.0)
        assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, "hidraw11")), (
            "a entrega abriu um controle novo com um cliente do broker conectado")

        seis.desconectar(conn)
        seis.tique(1.0)
        assert all(
            _aberto_para_a_sessao(c) for c in _tudo_do_aparelho(seis.mesa, "hidraw11"))

    def test_ping_status_e_open_nao_recolhem_a_entrega(self, seis: Cena) -> None:
        """A aba Conexões (outro processo, sem daemon) abre o nó pelo broker só
        para ler; o doctor pergunta o `status`. Nenhum dos dois é «o Hefesto
        voltou», e fechar o físico por causa deles desfaria o que o usuário
        pediu ao parar o serviço."""
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA)

        conn = seis.conectar()
        assert seis.pedir(conn, {"cmd": "ping"})["ok"]
        estado = seis.pedir(conn, {"cmd": "status"})
        assert estado["entregue"] is True
        seis.pedir(conn, {"cmd": "open", "node": seis.mesa.no("hidraw5")})
        assert seis.st.entregue is True
        for base, _ in OS_SEIS:
            assert all(_aberto_para_a_sessao(c) for c in _tudo_do_aparelho(seis.mesa, base))

    def test_ligar_e_desligar_de_novo_cabe_no_mesmo_broker(self, seis: Cena) -> None:
        """O ciclo inteiro duas vezes: parar, entregar, ligar, esconder, parar, entregar."""
        for _ in range(2):
            conn = seis.conectar()
            seis.o_daemon_esconde(conn, [b for b, _ in OS_SEIS])
            assert seis.st.entregue is False
            seis.desconectar(conn)
            seis.tique(GRACA)
            assert seis.st.entregue is True
            assert all(
                _aberto_para_a_sessao(c)
                for b, _ in OS_SEIS
                for c in _tudo_do_aparelho(seis.mesa, b)
            )


class TestOQueNaoMuda:
    def test_sem_a_cura_instalada_nao_ha_o_que_entregar(self, mesa: Mesa) -> None:
        """O nó do mundo antigo já nasce aberto: a entrega não existe nele."""
        mesa.nascer("hidraw5", "radio", 1, aberto=True)
        cena = Cena(mesa, no_nasce_fechado=False)
        conn = cena.conectar()
        cena.desconectar(conn)
        cena.tique(GRACA * 10)
        assert cena.st.entregue is False

    def test_graca_zero_desliga_a_entrega(self, mesa: Mesa) -> None:
        mesa.nascer("hidraw5", "radio", 1)
        cena = Cena(mesa, graca=0)
        conn = cena.conectar()
        cena.o_daemon_esconde(conn, ["hidraw5"])
        cena.desconectar(conn)
        cena.tique(GRACA * 10)
        assert cena.st.entregue is False
        assert _fechado(mesa.dev / "hidraw5")

    def test_um_cliente_vivo_segura_a_entrega(self, seis: Cena) -> None:
        """Enquanto o daemon estiver conectado, o broker nunca entrega, por mais
        que o relógio ande: a conexão É a lease."""
        conn = seis.conectar()
        seis.o_daemon_esconde(conn, [b for b, _ in OS_SEIS])
        seis.tique(GRACA * 100)
        assert seis.st.entregue is False
        assert all(_fechado(seis.mesa.dev / b) for b, _ in OS_SEIS)

    def test_cliente_conectado_sem_lease_tambem_segura_a_entrega(self, seis: Cena) -> None:
        """A espera conta SEM NENHUMA conexão: o daemon que acabou de conectar e
        ainda não escondeu nada (ou o doctor, só com `ping`) não é «Hefesto
        parado». MORDIDA: a conexão nova que não zera a espera entrega aqui."""
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA - 5)
        conn = seis.conectar()
        assert seis.pedir(conn, {"cmd": "ping"})["ok"]
        seis.tique(GRACA * 3)
        assert seis.st.entregue is False
        assert all(_fechado(seis.mesa.dev / b) for b, _ in OS_SEIS)

    def test_a_entrega_do_estado_nao_toca_no_que_alguem_segura(self, seis: Cena) -> None:
        """O estado se defende sozinho: com lease viva, `entregar_ao_linux` não faz nada."""
        conn = seis.conectar()
        seis.o_daemon_esconde(conn, [b for b, _ in OS_SEIS])
        assert seis.st.entregar_ao_linux() == []
        assert seis.st.entregue is False
        assert all(_fechado(seis.mesa.dev / b) for b, _ in OS_SEIS)

    def test_a_graca_e_a_medida_e_a_env_a_troca(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(hb.GRACA_DA_ENTREGA_ENV, raising=False)
        assert hb._graca_da_entrega_do_ambiente() == hb.GRACA_DA_ENTREGA_S
        monkeypatch.setenv(hb.GRACA_DA_ENTREGA_ENV, "7.5")
        assert hb._graca_da_entrega_do_ambiente() == 7.5
        monkeypatch.setenv(hb.GRACA_DA_ENTREGA_ENV, "abc")
        assert hb._graca_da_entrega_do_ambiente() == hb.GRACA_DA_ENTREGA_S

    def test_a_graca_cobre_o_pior_reinicio_medido(self) -> None:
        """15 s foi o maior vão entre o EOF e o primeiro pedido nos reinícios do
        diário de 05 a 08/10/2026. A graça é o dobro: baixá-la abaixo de 15 s
        entrega o físico no meio de um reinício."""
        assert hb.GRACA_DA_ENTREGA_S >= 2 * 15.0

    def test_a_mordida_sem_o_tique_o_fisico_fica_fechado(
        self, seis: Cena, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A prova de que as réguas acima medem a cura: sem ela, a bancada de 03/10."""
        monkeypatch.setattr(Broker, "tique_da_entrega", lambda self: None)
        _o_daemon_sobe_e_para(seis)
        seis.tique(GRACA * 10)
        assert seis.st.entregue is False
        for base, _ in OS_SEIS:
            assert all(_fechado(c) for c in _tudo_do_aparelho(seis.mesa, base))


def test_o_laco_do_broker_chama_o_tique(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `run()` é quem dá o tique: sem a chamada, a entrega existe e nunca dispara.

    O `step` é o que para o laço (3 voltas), para que a mordida REPROVE em vez
    de pendurar o teste."""
    voltas: list[int] = []
    tiques: list[int] = []
    broker = Broker(
        BrokerState(allowed_uid=UID, ops=object(), validator=lambda _n: None),
        None,
        log=lambda *_a, **_k: None,
    )

    def _step(timeout: float = 0.0) -> None:
        voltas.append(1)
        broker.stopping = len(voltas) >= 3

    monkeypatch.setattr(broker, "step", _step)
    monkeypatch.setattr(broker, "tique_da_entrega", lambda: tiques.append(1))
    monkeypatch.setattr(broker._state, "restore_everything", lambda: [])
    broker.run()
    assert len(voltas) == 3 and len(tiques) == 3
