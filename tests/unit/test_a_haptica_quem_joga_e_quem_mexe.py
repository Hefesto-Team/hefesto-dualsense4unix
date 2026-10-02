"""A-HAPTICA-QUEM-JOGA-01 — quem joga é o controle que MEXEU desde que o jogo abriu.

**O defeito, medido em 26/09/2026** (a vibração que sumiu no PRAGMATA): o
portão da háptica pelo rádio só deixa entrar quem o jogo LÊ, e quem respondia
contava os ``eventN`` que um processo de jogo segura. O winebus do GE-Proton
não segura evdev de DualSense NENHUM — só o ``hidraw``, e o de TODOS os vpads.
Com máscara DualSense a resposta saía vazia por construção: nenhum controle
vibrava, e o diário não dizia nada.

**A decisão** (``D-2609-QUEM-JOGA-E-QUEM-MEXE``, por delegação): quem joga é o
físico que teve entrada — botão, gatilho ou eixo fora da zona morta — desde
que o jogo abriu, somado ao endpoint dele tocando. Contar o ``hidraw``
devolveria o espelhado de 20/09 (o P3 vibrando num jogo de um jogador), e o
``eventN`` também não vota (A-HAPTICA-QUEM-JOGA-02): em 21/09 ele pôs os
quatro em háptica; aqui ele é só a pista ``evdev_le_este`` da linha do portão.

**O mundo destas réguas é o medido**, montado de mentira: um ``/proc`` com o
processo do jogo segurando só o ``hidraw`` dos vpads (e o de um teclado), a
Steam — sem a variável do Proton — segurando os mesmos vpads, o
``/sys/class/input`` e o ``/sys/class/hidraw`` com os físicos e os vpads, e o
jogo tocando no endpoint de TODO controle (o pior caso de 21/09). Nenhum
aparelho, nenhum servidor de som, nenhum ``/proc`` de verdade.

**E DESDE 28/09 A PARTIDA É O DONO DO FLUXO** (A-HAPTICA-DO-RADIO-OBEDECE-AO-
SINAL-DO-JOGO-01): o jogo abre quando o cliente dele toca nos endpoints, no
servidor de som de mentira (``ServidorDeSom``, que fala a linha curta do
``pactl``), e fecha quando ele se desconecta. O ``/proc`` fica para a PISTA da
linha do portão fechado, que só se pergunta quando a linha sai. O vigia de
0,4 s saiu: a linha sai na volta, e o primeiro toque acorda a volta pelo aviso.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` e os ``02:fe:00`` do vpad.
"""

from __future__ import annotations

import asyncio
import functools
import os
import pathlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.subsystems import quem_mexe as qm
from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    AltoFalanteSubsystem,
    ControleNaLista,
)
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations import quem_o_jogo_le as qjl
from tests.unit.test_a_haptica_do_radio_obedece_ao_sinal import ServidorDeSom
from tests.unit.test_haptica_por_radio_01_a_ponte_troca_de_modo import (
    _EndpointDeMentira,
    _PonteDeMentira,
)

#: A mesa de quatro, na grafia do sysfs (a da lista de controles).
P1, P2, P3, P4 = (f"aa:bb:cc:00:00:0{i}" for i in range(1, 5))
MESA = (P1, P2, P3, P4)
#: Os vpads que o produto forja, um por jogador.
VPADS = {u: f"02:fe:00:00:00:0{i}" for i, u in enumerate(MESA, start=1)}
#: O hidraw de cada vpad e de cada físico no rádio.
HIDRAW_DO_VPAD = {u: f"hidraw{i + 2}" for i, u in enumerate(MESA)}
HIDRAW_DO_FISICO = {u: f"hidraw{i + 10}" for i, u in enumerate(MESA)}
#: O pid do ``winedevice.exe`` e o do ``.exe`` do jogo; o da Steam, sem Proton.
PID_WINEDEVICE, PID_DO_EXE, PID_DA_STEAM = 4242, 4243, 100
#: O cliente do servidor de som que é o jogo — o ``winepulse`` do ``.exe``.
JOGO = "5150"


def assento(uniq: str) -> int | None:
    """O «Controle N» que o dono responde: a ordem da MESA; fora dela, «não sei»."""
    return MESA.index(uniq) + 1 if uniq in MESA else None


def no_do(uniq: str) -> str:
    """O endpoint do APARELHO deste controle — o dublê de ``_EndpointDeMentira``.

    O endpoint é do aparelho desde 02/10/2026 (A-HAPTICA-E-POR-APARELHO-01; de
    28/09 a 02/10 era do lugar em que o controle sentava).
    """
    return f"endpoint::{uniq}"


def colada(uniq: str) -> str:
    """``aa:bb:cc:00:00:02`` → ``aabbcc000002``: a grafia do co-op e do backend."""
    return uniq.replace(":", "")


# ---------------------------------------------------------------------------
# O mundo de mentira: /proc, /sys/class/input e /sys/class/hidraw
# ---------------------------------------------------------------------------


class Mundo:
    """O que o jogo segura, visto de fora — e nada lido da máquina."""

    def __init__(self, raiz: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.proc = raiz / "proc"
        self.dev = raiz / "dev"
        self.entrada = raiz / "input"
        self.hidraw = raiz / "hidraw"
        for pasta in (self.proc, self.dev / "input", self.entrada, self.hidraw):
            pasta.mkdir(parents=True)
        monkeypatch.setattr(qjl, "RAIZ_CLASS_HIDRAW", str(self.hidraw))
        monkeypatch.setattr(
            qjl,
            "quem_o_jogo_le",
            functools.partial(qjl.quem_o_jogo_le, raiz_proc=self.proc, raiz_input=self.entrada),
        )
        for i, uniq in enumerate(MESA):
            self._evento(f"event{30 + i}", uniq)
            self._evento(f"event{500 + i}", VPADS[uniq])
            self._hid(HIDRAW_DO_FISICO[uniq], phys="aa:bb:cc:00:00:ff", uniq=uniq)
            self._hid(HIDRAW_DO_VPAD[uniq], phys="hefesto-vpad", uniq=VPADS[uniq])
        self._hid("hidraw0", phys="usb-0000:0c:00.3-1.1.2/input0", uniq="")
        # A Steam segura os vpads o tempo todo, e NÃO é jogo.
        self.processo(PID_DA_STEAM, jogo=False, nos=[HIDRAW_DO_VPAD[u] for u in MESA])

    def _evento(self, nome: str, uniq: str) -> None:
        (self.entrada / nome / "device").mkdir(parents=True)
        (self.entrada / nome / "device" / "uniq").write_text(uniq + "\n")

    def _hid(self, nome: str, *, phys: str, uniq: str) -> None:
        (self.hidraw / nome / "device").mkdir(parents=True)
        (self.hidraw / nome / "device" / "uevent").write_text(
            f"DRIVER=playstation\nHID_PHYS={phys}\nHID_UNIQ={uniq}\n"
        )

    def processo(self, pid: int, *, jogo: bool, nos: list[str]) -> None:
        pasta = self.proc / str(pid)
        (pasta / "fd").mkdir(parents=True)
        env = "STEAM_COMPAT_DATA_PATH=/prefixo\0HOME=/x\0" if jogo else "HOME=/x\0"
        (pasta / "environ").write_bytes(env.encode())
        for fd, no in enumerate(nos, start=3):
            alvo = self.dev / "input" / no if no.startswith("event") else self.dev / no
            alvo.touch(exist_ok=True)
            os.symlink(alvo, pasta / "fd" / str(fd))

    def abrir_o_jogo_do_ge(self, *, pids: tuple[int, int] = (PID_WINEDEVICE, PID_DO_EXE)) -> None:
        """O GE de 26/09: o winedevice segura o hidraw de TODOS os vpads e nenhum evdev."""
        winedevice, exe = pids
        self.processo(winedevice, jogo=True, nos=[*(HIDRAW_DO_VPAD[u] for u in MESA), "hidraw0"])
        self.processo(exe, jogo=True, nos=[])

    def fechar_o_jogo(self) -> None:
        for pasta in list(self.proc.iterdir()):
            if pasta.name != str(PID_DA_STEAM):
                for fd in (pasta / "fd").iterdir():
                    fd.unlink()
                (pasta / "fd").rmdir()
                (pasta / "environ").unlink()
                pasta.rmdir()


# ---------------------------------------------------------------------------
# A bancada: o subsystem de verdade, com a ponte e o endpoint de mentira
# ---------------------------------------------------------------------------


class Bancada:
    """O ``_casar_as_pontes`` do produto; a fiação de som e o servidor são dublês."""

    def __init__(
        self,
        mundo: Mundo,
        monkeypatch: pytest.MonkeyPatch,
        *,
        transportes: dict[str, str] | None = None,
    ) -> None:
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
        from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

        self.mundo = mundo
        _PonteDeMentira.criadas = []
        _EndpointDeMentira.criados = []
        _EndpointDeMentira.quedas = []
        #: O servidor de som: quem toca em qual endpoint, e de quem é o fluxo.
        self.servidor = ServidorDeSom()
        monkeypatch.setattr(af, "rodar_pactl", self.servidor)
        monkeypatch.setattr(
            af, "fonte_do_monitor_do_no", lambda nome, **kw: ((lambda _n: b""), f"g:{nome}", "")
        )
        monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
        monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
        monkeypatch.setattr(
            eh,
            "ancoras",
            lambda *a, **k: [
                eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in range(4)
            ],
        )
        monkeypatch.setattr(eh, "endpoints_de_pe", lambda *a, **k: {})
        monkeypatch.setattr(eh, "varrer_endpoints_orfaos", lambda *a, **k: None)
        monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
        #: O co-op responde quem alimenta cada vpad — a pista do evdev o consulta.
        coop = SimpleNamespace(
            quem_alimenta_cada_vpad=lambda: {VPADS[u]: colada(u) for u in MESA}
        )
        self.daemon = SimpleNamespace(_coop_manager=coop)
        self.sub = AltoFalanteSubsystem(daemon=self.daemon)
        monkeypatch.setattr(
            AltoFalanteSubsystem, "numero_do_assento", lambda _self, u: assento(u)
        )
        # O aviso de quem entra na partida, como o `start()` o liga.
        self.sub._ouvir_quem_entra_na_partida(self.sub._acordar_a_volta)
        vias = transportes or {}
        self.controles = [
            ControleNaLista(
                uniq=u, caminho=f"/dev/{HIDRAW_DO_FISICO[u]}", transporte=vias.get(u, "rádio")
            )
            for u in MESA
        ]

    def abrir_o_jogo(self, *, cliente: str = JOGO, pids: tuple[int, int] | None = None) -> None:
        """O GE abre: o ``/proc`` da pista, e o fluxo do jogo em TODO endpoint (21/09)."""
        if pids is None:
            self.mundo.abrir_o_jogo_do_ge()
        else:
            self.mundo.abrir_o_jogo_do_ge(pids=pids)
        for uniq in MESA:
            self.servidor.tocar(no_do(uniq), cliente)

    def fechar_o_jogo(self, *, cliente: str = JOGO) -> None:
        self.mundo.fechar_o_jogo()
        self.servidor.desconectar(cliente)

    @property
    def marcas(self) -> qm.QuemMexe:
        marcas = qm.quem_mexe_de(self.daemon)
        assert marcas is not None
        return marcas

    def volta(self) -> set[str]:
        """Uma volta do portão; devolve quem está em modo háptica."""
        self.sub._casar_as_pontes(self.controles)
        return {u for u, modo in self.sub._modo_da_ponte.items() if modo == "haptica"}

    def mexer(self, uniq: str) -> None:
        """A mão no controle: o analógico esquerdo no talo, como o laço leria."""
        self.marcas.anotar(
            colada(uniq), botoes=frozenset(), lx=255, ly=128, rx=128, ry=128, l2=0, r2=0
        )


@pytest.fixture
def mundo(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Mundo:
    return Mundo(tmp_path, monkeypatch)


@pytest.fixture
def bancada(mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> Bancada:
    return Bancada(mundo, monkeypatch)


# ---------------------------------------------------------------------------
# (a) O mundo medido
# ---------------------------------------------------------------------------


class TestOMundoMedido:
    """O GE segura o hidraw dos quatro vpads e nenhum evdev; só quem mexeu vibra."""

    def test_so_o_controle_que_mexeu_entra_em_haptica(self, bancada: Bancada) -> None:
        """A régua da sprint.

        MORDIDA: troque ``jogando = self._quem_mexeu_na_partida(controles)``
        por ``set()`` no ``_casar_as_pontes`` — ninguém entra (o defeito de
        26/09). E trocar o sinal por «o jogo segura o hidraw do vpad» põe os
        QUATRO: o mundo abaixo prova que o jogo segura os quatro.
        """
        bancada.abrir_o_jogo()
        assert bancada.volta() == set(), "a partida abriu agora: ninguém mexeu ainda"
        assert bancada.marcas.jogo_aberto is True, "o fluxo do jogo não abriu a partida"
        retrato = bancada.sub._retrato_do_jogo
        assert retrato is not None, "a linha do portão fechado não perguntou a pista"
        assert retrato.eventos == frozenset(), "o GE não segura evdev de DualSense"
        assert qjl.hidraws_de_vpad(retrato.hidraws) == {HIDRAW_DO_VPAD[u] for u in MESA}, (
            "o mundo não é o medido: o jogo segura o hidraw de todos os vpads"
        )
        bancada.mexer(P2)
        assert bancada.volta() == {P2}

    def test_o_primeiro_toque_acorda_a_volta_pelo_aviso(self, bancada: Bancada) -> None:
        """O toque avisa a volta, sem esperar a seguinte (5 s) e sem vigia perguntando.

        MORDIDA: tire a chamada a ``ao_marcar`` de ``QuemMexe.marcar`` — a volta
        não é pedida.
        """
        bancada.abrir_o_jogo()
        bancada.volta()
        assert bancada.sub._volta_pedida is False, "sem toque, nada a reconciliar"
        bancada.mexer(P3)
        assert bancada.sub._volta_pedida is True
        assert bancada.volta() == {P3}

    def test_a_steam_segurando_os_vpads_sem_jogo_nao_abre_partida(self, bancada: Bancada) -> None:
        """A Steam escreve nos vpads antes de o jogo abrir, e não é jogo."""
        bancada.volta()
        bancada.mexer(P1)
        assert bancada.marcas.jogo_aberto is False
        assert bancada.volta() == set()


# ---------------------------------------------------------------------------
# O fd aberto não vota — A-HAPTICA-QUEM-JOGA-02
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nos",
    [[f"event{500 + i}" for i in range(4)], [f"event{30 + i}" for i in range(4)]],
    ids=["evdev-dos-quatro-vpads", "evdev-dos-quatro-fisicos"],
)
def test_o_evdev_cheio_nao_poe_ninguem_em_haptica(bancada: Bancada, nos: list[str]) -> None:
    """Um processo de jogo segura o ``eventN`` dos quatro, e só o P2 mexeu: só o P2 vibra.

    O mundo que as réguas acima não montam: nelas o GE não segura evdev nenhum,
    e uma união com o evdev passaria sem nunca ter sido medida cheia. Em 21/09,
    às 01:51, com o PRAGMATA de um jogador, o portão pôs os QUATRO em háptica, e
    o único sinal daquele código era o evdev (conferência de 26/09, §2.1). O
    detentor não foi achado; se ele voltar — ou se um Proton segurar o evdev dos
    vpads, como o SDL faz com todo controle —, o evdev diz «o jogo lê os
    quatro». O primeiro caso é o dos vpads (o tradutor do co-op liga cada um ao
    físico que o alimenta); o segundo, o de 21/09, com os físicos.

    MORDIDA: devolva ``jogando |= <o que o evdev traduz>`` ao ``_casar_as_pontes``
    — os quatro entram antes de alguém tocar num controle.
    """
    bancada.abrir_o_jogo()
    bancada.mundo.processo(4400, jogo=True, nos=nos)
    with structlog.testing.capture_logs() as registros:
        assert bancada.volta() == set(), "o fd aberto pôs em háptica quem não tocou no controle"
    linhas = _linhas(registros)
    assert {r["uniq"] for r in linhas} == set(MESA)
    assert {r["evdev_le_este"] for r in linhas} == {True}, (
        "a pista do evdev tem de chegar ao diário: é por ela que o detentor aparece"
    )
    bancada.mexer(P2)
    assert bancada.volta() == {P2}


def test_a_pergunta_ao_coop_que_falha_nao_segura_a_partida(bancada: Bancada) -> None:
    """O co-op levanta quando o jogo abre, e mesmo assim a partida abre e o P3 entra.

    A partida não precisa do co-op — é o fluxo no endpoint; só a pista do evdev
    precisa dele, e o erro dela vai ao diário sem levar a volta junto.

    MORDIDA: tire o ``try`` da pergunta ao co-op em ``_quem_o_jogo_le`` — a
    exceção sobe da linha do portão e a volta cai.
    """

    def _falha() -> dict[str, str]:
        raise RuntimeError("a mesa mudou no meio")

    bancada.daemon._coop_manager = SimpleNamespace(quem_alimenta_cada_vpad=_falha)
    bancada.abrir_o_jogo()
    with structlog.testing.capture_logs() as registros:
        assert bancada.volta() == set()
    assert "haptica_nao_sei_quem_joga" in [r["event"] for r in registros], (
        "o erro do co-op tem de ir ao diário"
    )
    assert bancada.marcas.jogo_aberto is True, "o erro do co-op segurou a partida fechada"
    bancada.mexer(P3)
    assert bancada.volta() == {P3}


# ---------------------------------------------------------------------------
# (b) De um a quatro jogadores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "quem",
    [(P1,), (P3,), (P2, P4), (P1, P2, P3), MESA],
    ids=["p1", "p3", "p2-e-p4", "p1-p2-p3", "os-quatro"],
)
def test_cada_um_que_mexe_entra_e_so_ele(bancada: Bancada, quem: tuple[str, ...]) -> None:
    """Nenhum índice é privilegiado, e a mesa de quatro entra inteira.

    MORDIDA: cravar o P1 (``{P1}``) no lugar da marca — quatro de cinco reprovam.
    """
    bancada.abrir_o_jogo()
    bancada.volta()
    for uniq in quem:
        bancada.mexer(uniq)
    assert bancada.volta() == set(quem)


def test_o_do_cabo_mexe_e_nao_ganha_ponte(mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> None:
    """No cabo a háptica é a placa de som do controle: o portão do rádio não o toca."""
    bancada = Bancada(mundo, monkeypatch, transportes={P1: "cabo"})
    bancada.abrir_o_jogo()
    bancada.volta()
    for uniq in MESA:
        bancada.mexer(uniq)
    assert bancada.volta() == {P2, P3, P4}


# ---------------------------------------------------------------------------
# (c) O jogo fecha, a marca zera
# ---------------------------------------------------------------------------


class TestAPartida:
    def test_o_jogo_que_fecha_zera_a_marca(self, bancada: Bancada) -> None:
        """O cliente do jogo sai do servidor: a partida fecha e ninguém fica.

        MORDIDA: tire o ramo que fecha de ``acompanhar_o_jogo`` — a partida
        segue aberta e a marca do P2 vale no próximo jogo.
        """
        bancada.abrir_o_jogo()
        bancada.volta()
        bancada.mexer(P2)
        assert bancada.volta() == {P2}
        bancada.fechar_o_jogo()
        assert bancada.volta() == set()
        assert bancada.marcas.jogo_aberto is False
        assert bancada.marcas.quem_joga() == frozenset()

    def test_o_jogo_que_reabre_pede_entrada_nova(self, bancada: Bancada) -> None:
        """A marca é da partida: a de ontem não vale no jogo de hoje.

        MORDIDA: tire as DUAS limpezas (``self._marcas = {}`` do ramo que abre
        e do que fecha) — o P2 entra na partida nova sem tocar no controle.
        """
        bancada.abrir_o_jogo()
        bancada.volta()
        bancada.mexer(P2)
        bancada.volta()
        bancada.fechar_o_jogo()
        bancada.volta()
        bancada.abrir_o_jogo(cliente="6160")
        assert bancada.volta() == set()
        bancada.mexer(P4)
        assert bancada.volta() == {P4}

    def test_outro_jogo_sem_passar_pelo_vazio_zera_a_marca(self, bancada: Bancada) -> None:
        """Um jogo fecha e outro abre entre duas voltas: nenhum dono de antes segue vivo.

        MORDIDA: tire o ``self._abrir(agora)`` do ramo do dono novo sem
        sobrevivente — a marca do jogo de antes vale no novo.
        """
        bancada.abrir_o_jogo()
        bancada.volta()
        bancada.mexer(P2)
        assert bancada.volta() == {P2}
        bancada.fechar_o_jogo()
        bancada.abrir_o_jogo(cliente="6160", pids=(5000, 5001))
        assert bancada.volta() == set()

    def test_o_mesmo_jogo_com_outro_cliente_segue_a_partida(self, bancada: Bancada) -> None:
        """Um segundo cliente do jogo abre fluxo com o primeiro vivo: é o mesmo jogo."""
        bancada.abrir_o_jogo()
        bancada.volta()
        bancada.mexer(P2)
        bancada.servidor.tocar(no_do(P2), "5151")
        assert bancada.volta() == {P2}

    def test_o_jogo_que_fecha_o_fluxo_e_segue_vivo_nao_zera(self, bancada: Bancada) -> None:
        """O GE remira a háptica a cada hotplug de endpoint: o fluxo cai e volta."""
        bancada.abrir_o_jogo()
        bancada.volta()
        bancada.mexer(P2)
        bancada.servidor.calar(JOGO)
        bancada.volta()
        assert bancada.marcas.joga(P2), "o fluxo que caiu com o jogo vivo zerou a marca"
        for uniq in MESA:
            bancada.servidor.tocar(no_do(uniq), JOGO)
        assert bancada.volta() == {P2}

    def test_o_servidor_mudo_nao_fecha_a_partida(self, bancada: Bancada) -> None:
        """Na dúvida, não mexe: o servidor que não responde não zera quem joga."""
        bancada.abrir_o_jogo()
        bancada.volta()
        bancada.mexer(P2)
        bancada.volta()
        bancada.servidor.mudo = True
        bancada.volta()
        assert bancada.marcas.jogo_aberto is True
        assert bancada.marcas.joga(P2)


# ---------------------------------------------------------------------------
# (d) O portão diz por que fechou — uma vez, na mudança
# ---------------------------------------------------------------------------


def _linhas(registros: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in registros if r["event"] == "haptica_portao_fechado"]


class TestOPortaoDizPorQueFechou:
    def test_uma_linha_por_controle_e_so_na_mudanca(self, bancada: Bancada) -> None:
        """O PRAGMATA de 26/09 ficou sete minutos no estado anômalo sem uma linha.

        MORDIDA: tire o ``if anterior == motivo: return`` de
        ``_vigiar_o_portao`` — doze linhas em vez de quatro.

        A linha que o PRAGMATA teria escrito é ``evdev_do_jogo=0
        hidraw_de_vpad=2`` (dois vpads na mesa dela); aqui são quatro.
        """
        bancada.abrir_o_jogo()
        with structlog.testing.capture_logs() as registros:
            for _ in range(3):
                bancada.volta()
        linhas = _linhas(registros)
        assert sorted(r["uniq"] for r in linhas) == sorted(MESA)
        assert {r["motivo"] for r in linhas} == {"nao_mexeu"}
        assert {(r["evdev_do_jogo"], r["hidraw_de_vpad"]) for r in linhas} == {(0, 4)}, (
            "a linha tem de dizer o que o jogo segura: nenhum evdev, os quatro vpads"
        )

    def test_quem_mexe_sai_do_estado_calado_e_volta_dizendo(self, bancada: Bancada) -> None:
        bancada.abrir_o_jogo()
        bancada.volta()
        bancada.mexer(P1)
        with structlog.testing.capture_logs() as registros:
            bancada.volta()
        assert _linhas(registros) == [], "sair do estado anômalo não loga"
        # O jogo fecha e um módulo segue tocando nos endpoints (sem cliente): o
        # endpoint toca, e não há jogo.
        bancada.fechar_o_jogo()
        for uniq in MESA:
            bancada.servidor.tocar(no_do(uniq), "-")
        with structlog.testing.capture_logs() as registros:
            bancada.volta()
            bancada.volta()
        motivos = {r["uniq"]: r["motivo"] for r in _linhas(registros)}
        # O P1 voltou ao estado; os outros três mudaram de motivo. Uma linha cada.
        assert motivos == {u: "sem_jogo" for u in MESA}
        assert len(_linhas(registros)) == len(MESA)

    def test_o_repouso_nao_loga(self, bancada: Bancada) -> None:
        """Endpoint sem fluxo é o repouso de todo controle fora de jogo."""
        with structlog.testing.capture_logs() as registros:
            bancada.volta()
        assert _linhas(registros) == []

    def test_o_sysfs_que_falha_nao_derruba_a_volta(
        self, bancada: Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A linha sai sem a contagem, e a volta segue.

        MORDIDA: tire o ``try`` de ``_o_que_o_jogo_segura`` — a exceção sobe
        da linha do portão, e na produção a volta inteira cairia.
        """

        def _quebra(_nomes: Any) -> frozenset[str]:
            raise RuntimeError("sysfs sumiu no meio")

        bancada.abrir_o_jogo()
        monkeypatch.setattr(qjl, "hidraws_de_vpad", _quebra)
        with structlog.testing.capture_logs() as registros:
            bancada.volta()
        linhas = _linhas(registros)
        assert len(linhas) == len(MESA)
        assert {(r["evdev_do_jogo"], r["hidraw_de_vpad"]) for r in linhas} == {(None, None)}

    def test_o_endereco_sai_mascarado(self, mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> None:
        """Octetos 4 e 5 zerados, como o diário da bateria já faz.

        MORDIDA: logue o ``uniq`` cru.
        """
        bancada = Bancada(mundo, monkeypatch)
        bancada.controles = [
            ControleNaLista(uniq="aa:bb:cc:12:34:05", caminho="/dev/hidraw19", transporte="rádio")
        ]
        bancada.servidor.tocar(no_do("aa:bb:cc:12:34:05"), "-")
        with structlog.testing.capture_logs() as registros:
            bancada.volta()
        assert [r["uniq"] for r in _linhas(registros)] == ["aa:bb:cc:00:00:05"]
        assert _linhas(registros)[0]["motivo"] == "sem_jogo"

    def test_o_dono_que_nao_se_le_diz_nao_sei(
        self, bancada: Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem saber de quem é o fluxo, o motivo é ``nao_sei`` — não ``sem_jogo``.

        MORDIDA: faça ``_por_que_o_portao_fecha`` responder ``nao_mexeu`` com
        os donos desconhecidos — a linha afirma sobre um jogo que ninguém viu.
        """
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        def _quebra(*_a: Any, **_k: Any) -> frozenset[str]:
            raise OSError("o servidor caiu no meio da pergunta")

        bancada.abrir_o_jogo()
        monkeypatch.setattr(af, "donos_dos_fluxos", _quebra)
        with structlog.testing.capture_logs() as registros:
            bancada.volta()
        assert {r["motivo"] for r in _linhas(registros)} == {"nao_sei"}

    def test_quem_sai_da_mesa_e_volta_no_mesmo_estado_diz_de_novo(self, bancada: Bancada) -> None:
        """O controle que cai e volta no meio do jogo é outro endpoint: a linha sai de novo.

        MORDIDA: tire a poda de ``_portao_fechado`` do ``_casar_as_pontes`` — o
        P4 volta calado, porque a volta ainda lembra o motivo de antes da queda.
        """
        bancada.abrir_o_jogo()
        bancada.volta()
        todos = bancada.controles
        bancada.controles = [c for c in todos if c.uniq != P4]
        bancada.volta()
        bancada.controles = todos
        with structlog.testing.capture_logs() as registros:
            bancada.volta()
        assert [r["uniq"] for r in _linhas(registros)] == [P4]


# ---------------------------------------------------------------------------
# A fiação: quem marca, e com o que já leu
# ---------------------------------------------------------------------------


class _Leitor:
    def __init__(self, **eixos: Any) -> None:
        self.eixos = {"l2_raw": 0, "r2_raw": 0, "lx": 128, "ly": 128, "rx": 128, "ry": 128}
        self.eixos.update(eixos)
        self.botoes: frozenset[str] = frozenset()

    def snapshot(self) -> Any:
        return SimpleNamespace(buttons_pressed=self.botoes, **self.eixos)


class _Vpad:
    def forward_analog(self, **_: Any) -> None:
        return None

    def forward_buttons(self, _b: Any) -> None:
        return None


def _partida_aberta() -> qm.QuemMexe:
    marcas = qm.QuemMexe()
    marcas.acompanhar_o_jogo({PID_WINEDEVICE})
    return marcas


class TestAFiacao:
    def test_o_forward_all_marca_o_secundario_que_mexeu(self) -> None:
        """MORDIDA: tire o ``marcas.anotar(...)`` do ``forward_all``; ou a zona
        morta de ``teve_entrada`` (o parado, com 3 de drift, entra)."""
        daemon = SimpleNamespace(
            controller=SimpleNamespace(primary_uniq=colada(P1), _evdev=None),
            _gamepad_device=_Vpad(),
            config=SimpleNamespace(coop_enabled=True),
            _quem_mexe=_partida_aberta(),
        )
        coop = CoopManager(daemon)  # type: ignore[arg-type]
        parado, mexendo = _Leitor(lx=131, ly=125), _Leitor(ry=20)
        coop._players = {
            colada(u): _SecondaryPlayer(
                identity=colada(u),
                evdev_path=f"/dev/input/event{n}",
                reader=leitor,  # type: ignore[arg-type]
                player_index=n,
                vpad=_Vpad(),  # type: ignore[arg-type]
            )
            for n, (u, leitor) in enumerate(((P2, parado), (P3, mexendo)), start=2)
        }
        coop.forward_all()
        assert colada(P3) in daemon._quem_mexe.quem_joga(), "o forward_all não marcou quem mexeu"
        assert colada(P2) not in daemon._quem_mexe.quem_joga(), "o drift de 3 não é mão"

    def test_sem_partida_o_forward_all_nao_marca(self) -> None:
        daemon = SimpleNamespace(
            controller=SimpleNamespace(primary_uniq=colada(P1), _evdev=None),
            _gamepad_device=_Vpad(),
            config=SimpleNamespace(coop_enabled=True),
            _quem_mexe=qm.QuemMexe(),
        )
        coop = CoopManager(daemon)  # type: ignore[arg-type]
        coop._players = {
            colada(P2): _SecondaryPlayer(
                identity=colada(P2),
                evdev_path="/dev/input/event2",
                reader=_Leitor(lx=0),  # type: ignore[arg-type]
                player_index=2,
                vpad=_Vpad(),  # type: ignore[arg-type]
            )
        }
        coop.forward_all()
        daemon._quem_mexe.acompanhar_o_jogo({PID_WINEDEVICE})
        assert daemon._quem_mexe.quem_joga() == frozenset(), "a mão de antes do jogo não conta"

    @pytest.mark.asyncio
    async def test_o_laco_do_daemon_marca_o_primario_sem_snapshot_a_mais(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O laço de verdade, com o controle de mentira: o P1 com o gatilho no fundo.

        MORDIDA: tire a chamada a ``anotar_o_primario`` do ``_poll_loop``.
        E o snapshot segue um por tique (a régua do cache do evdev).
        """
        daemon, ticks, chamadas = await _rodar_o_laco(monkeypatch, assentamento_s=0.0)
        assert daemon._quem_mexe.quem_joga() == {colada(P1)}  # type: ignore[attr-defined]
        assert chamadas == ticks, "um snapshot por tique"

    @pytest.mark.asyncio
    async def test_o_fantasma_da_reconexao_nao_marca_o_primario(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Com o assentamento armado, o gatilho no fundo é o fantasma da conexão.

        A-HAPTICA-QUEM-JOGA-02. O BUG-DAEMON-CONNECT-GHOST-INPUT-01 arma o
        ``_input_ready_at`` na borda desconectado→conectado, e todo input fica
        suprimido até ele passar. Um controle PARADO que cai e volta no meio da
        partida entraria em háptica pelo lixo da primeira leitura — o espelhado
        de 20/09 pela porta da reconexão.

        MORDIDA: tire ``anotar_o_primario`` de dentro do ``if grace_passed:`` —
        o primário é marcado sem ninguém tocar nele.
        """
        daemon, ticks, _ = await _rodar_o_laco(monkeypatch, assentamento_s=600.0)
        assert ticks >= 5, "o laço não tiquetaqueou dentro do assentamento"
        assert daemon._quem_mexe.quem_joga() == frozenset(), (  # type: ignore[attr-defined]
            "o fantasma da reconexão marcou o primário"
        )


async def _rodar_o_laco(
    monkeypatch: pytest.MonkeyPatch, *, assentamento_s: float
) -> tuple[Any, int, int]:
    """O ``_poll_loop`` de verdade por cinco tiques, com o P1 de gatilho no fundo.

    Devolve o daemon, os tiques e quantos snapshots do evdev foram pedidos.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", assentamento_s
    )
    estados = [
        ControllerState(battery_pct=80, l2_raw=255, r2_raw=0, connected=True, transport="bt")
        for _ in range(200)
    ]
    fc = FakeController(transport="bt", states=estados)
    fc.primary_uniq = colada(P1)  # type: ignore[attr-defined]
    chamadas: list[int] = []
    evdev = MagicMock()
    evdev.is_available.return_value = True
    evdev.snapshot.side_effect = lambda: chamadas.append(1) or SimpleNamespace(
        buttons_pressed=[]
    )
    fc._evdev = evdev
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    daemon._quem_mexe = _partida_aberta()  # type: ignore[attr-defined]
    tarefa = asyncio.create_task(daemon.run())
    # Espera o LAÇO, e não um relógio: a subida dos subsystems varia com a
    # máquina, e um tempo fixo mediria a subida em vez do tique.
    for _ in range(300):
        if daemon.store.counter("poll.tick") >= 5:
            break
        await asyncio.sleep(0.01)
    daemon.stop()
    await tarefa
    ticks = daemon.store.counter("poll.tick")
    assert ticks >= 5, "o laço não tiquetaqueou"
    return daemon, ticks, len(chamadas)


# ---------------------------------------------------------------------------
# A entrada que conta, e o dono único
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "conta"),
    [
        ({}, False),
        ({"lx": 128 + qm.ZONA_MORTA}, False),
        ({"ly": 128 - qm.ZONA_MORTA}, False),
        ({"rx": 128 + qm.ZONA_MORTA + 1}, True),
        ({"ry": 0}, True),
        ({"l2": qm.ZONA_MORTA}, False),
        ({"r2": qm.ZONA_MORTA + 1}, True),
        ({"botoes": frozenset({"cross"})}, True),
    ],
    ids=["repouso", "drift-no-limite", "drift-para-cima", "eixo", "talo", "gatilho-no-limite",
         "gatilho", "botao"],
)
def test_a_entrada_que_conta(entrada: dict[str, Any], conta: bool) -> None:
    """MORDIDA: troque a zona morta por zero — o drift e o gatilho encostado contam."""
    base: dict[str, Any] = {
        "botoes": frozenset(), "lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2": 0, "r2": 0
    }
    assert qm.teve_entrada(**{**base, **entrada}) is conta


def test_o_dono_unico_nao_confia_num_mock() -> None:
    """Num ``MagicMock`` o ``getattr`` devolve um mock, e um mock diz «sim» a tudo."""
    daemon = MagicMock()
    marcas = qm.quem_mexe_de(daemon)
    assert isinstance(marcas, qm.QuemMexe)
    assert qm.quem_mexe_de(daemon) is marcas
    assert marcas.joga(P1) is False
    assert qm.marcas_da_partida(MagicMock()) is None
    assert qm.quem_mexe_de(None) is None
