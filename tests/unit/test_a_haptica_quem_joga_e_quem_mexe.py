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
devolveria o espelhado de 20/09 (o P3 vibrando num jogo de um jogador).

**O mundo destas réguas é o medido**, montado de mentira: um ``/proc`` com o
processo do jogo segurando só o ``hidraw`` dos vpads (e o de um teclado), a
Steam — sem a variável do Proton — segurando os mesmos vpads, o
``/sys/class/input`` e o ``/sys/class/hidraw`` com os físicos e os vpads, e o
jogo tocando no endpoint de TODO controle (o pior caso de 21/09). Nenhum
aparelho, nenhum servidor de som, nenhum ``/proc`` de verdade.

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
    """O ``_casar_as_pontes`` e o vigia do produto; só a fiação de som é dublê."""

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
        #: O jogo toca no endpoint de TODO controle — o pior caso de 21/09.
        self.endpoint_toca: dict[str, bool] = {u: True for u in MESA}
        monkeypatch.setattr(
            af, "fonte_do_monitor_do_no", lambda nome, **kw: ((lambda _n: b""), f"g:{nome}", "")
        )
        monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
        monkeypatch.setattr(af, "sink_esta_tocando", self._toca)
        monkeypatch.setattr(af, "sinks_que_tocam", self._tocam)
        monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
        monkeypatch.setattr(
            eh,
            "ancoras",
            lambda *a, **k: [
                eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in range(4)
            ],
        )
        monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
        #: O co-op responde quem alimenta cada vpad — e, sem evdev, nem é consultado.
        coop = SimpleNamespace(
            quem_alimenta_cada_vpad=lambda: {VPADS[u]: colada(u) for u in MESA}
        )
        self.daemon = SimpleNamespace(_coop_manager=coop)
        self.sub = AltoFalanteSubsystem(daemon=self.daemon)
        vias = transportes or {}
        self.controles = [
            ControleNaLista(
                uniq=u, caminho=f"/dev/{HIDRAW_DO_FISICO[u]}", transporte=vias.get(u, "rádio")
            )
            for u in MESA
        ]

    def _toca(self, nome: str, *_a: Any, **_k: Any) -> bool:
        """Só o endpoint de háptica toca; o alto-falante (o nó do som) está calado."""
        prefixo = "endpoint::"
        return nome.startswith(prefixo) and self.endpoint_toca.get(nome[len(prefixo):], False)

    def _tocam(self, nomes: Any) -> set[str]:
        return {n for n in nomes if n and self._toca(n)}

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

    def vigiar(self) -> bool:
        return self.sub._o_modo_de_alguem_mudou()


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

        MORDIDA: tire ``jogando |= self._quem_mexeu_na_partida(controles)`` do
        ``_casar_as_pontes`` — ninguém entra (o defeito de 26/09). E trocar o
        sinal por «o jogo segura o hidraw do vpad» põe os QUATRO: o mundo
        abaixo prova que o jogo segura os quatro.
        """
        bancada.mundo.abrir_o_jogo_do_ge()
        assert bancada.volta() == set(), "a partida abriu agora: ninguém mexeu ainda"
        retrato = bancada.sub._retrato_do_jogo
        assert retrato is not None, "a volta não guardou o que viu do jogo"
        assert retrato.eventos == frozenset(), "o GE não segura evdev de DualSense"
        assert qjl.hidraws_de_vpad(retrato.hidraws) == {HIDRAW_DO_VPAD[u] for u in MESA}, (
            "o mundo não é o medido: o jogo segura o hidraw de todos os vpads"
        )
        bancada.mexer(P2)
        assert bancada.volta() == {P2}

    def test_o_primeiro_toque_acorda_a_volta_pelo_vigia(self, bancada: Bancada) -> None:
        """O vigia vê a marca viva, sem esperar a volta seguinte (5 s).

        MORDIDA: tire ``marcas.joga(uniq)`` do vigia — ele não acorda.
        """
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        assert bancada.vigiar() is False, "sem toque, nada a reconciliar"
        bancada.mexer(P3)
        assert bancada.vigiar() is True
        assert bancada.volta() == {P3}

    def test_a_steam_segurando_os_vpads_sem_jogo_nao_abre_partida(self, bancada: Bancada) -> None:
        """A Steam escreve nos vpads antes de o jogo abrir, e não é jogo."""
        bancada.volta()
        bancada.mexer(P1)
        assert bancada.marcas.jogo_aberto is False
        assert bancada.volta() == set()


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
    bancada.mundo.abrir_o_jogo_do_ge()
    bancada.volta()
    for uniq in quem:
        bancada.mexer(uniq)
    assert bancada.volta() == set(quem)


def test_o_do_cabo_mexe_e_nao_ganha_ponte(mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> None:
    """No cabo a háptica é a placa de som do controle: o portão do rádio não o toca."""
    bancada = Bancada(mundo, monkeypatch, transportes={P1: "cabo"})
    mundo.abrir_o_jogo_do_ge()
    bancada.volta()
    for uniq in MESA:
        bancada.mexer(uniq)
    assert bancada.volta() == {P2, P3, P4}


# ---------------------------------------------------------------------------
# (c) O jogo fecha, a marca zera
# ---------------------------------------------------------------------------


class TestAPartida:
    def test_o_jogo_que_fecha_zera_a_marca(self, bancada: Bancada) -> None:
        """Com o endpoint ainda tocando (o «Testar», outro programa), ninguém fica.

        MORDIDA: tire o ramo do jogo fechado de ``acompanhar_o_jogo`` — a
        partida segue aberta e o P2 vibra sem jogo.
        """
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        bancada.mexer(P2)
        assert bancada.volta() == {P2}
        bancada.mundo.fechar_o_jogo()
        assert bancada.volta() == set()
        assert bancada.marcas.jogo_aberto is False
        assert bancada.marcas.quem_joga() == frozenset()

    def test_o_jogo_que_reabre_pede_entrada_nova(self, bancada: Bancada) -> None:
        """A marca é da partida: a de ontem não vale no jogo de hoje.

        MORDIDA: tire as DUAS limpezas (``self._marcas = {}`` do ramo que abre
        e do que fecha) — o P2 entra na partida nova sem tocar no controle.
        """
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        bancada.mexer(P2)
        bancada.volta()
        bancada.mundo.fechar_o_jogo()
        bancada.volta()
        bancada.mundo.abrir_o_jogo_do_ge()
        assert bancada.volta() == set()
        bancada.mexer(P4)
        assert bancada.volta() == {P4}

    def test_outro_jogo_sem_passar_pelo_vazio_zera_a_marca(self, bancada: Bancada) -> None:
        """Um jogo fecha e outro abre entre duas voltas: pids sem nada em comum.

        MORDIDA: tire o ``self._marcas = {}`` do ramo que ABRE a partida.
        """
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        bancada.mexer(P2)
        assert bancada.volta() == {P2}
        bancada.mundo.fechar_o_jogo()
        bancada.mundo.abrir_o_jogo_do_ge(pids=(5000, 5001))
        assert bancada.volta() == set()

    def test_o_mesmo_jogo_que_troca_de_processo_segue_a_partida(self, bancada: Bancada) -> None:
        """Um processo filho que nasce ou morre não é outro jogo."""
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        bancada.mexer(P2)
        bancada.mundo.processo(4300, jogo=True, nos=[])
        assert bancada.volta() == {P2}

    def test_a_pergunta_que_falha_nao_fecha_a_partida(self, bancada: Bancada) -> None:
        """Na dúvida, não mexe: um erro do co-op não zera quem está jogando."""
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        bancada.mexer(P2)

        def _falha() -> dict[str, str]:
            raise RuntimeError("a mesa mudou no meio")

        bancada.daemon._coop_manager = SimpleNamespace(quem_alimenta_cada_vpad=_falha)
        assert bancada.volta() == {P2}
        assert bancada.marcas.jogo_aberto is True


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
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        with structlog.testing.capture_logs() as registros:
            for _ in range(3):
                bancada.vigiar()
        linhas = _linhas(registros)
        assert sorted(r["uniq"] for r in linhas) == sorted(MESA)
        assert {r["motivo"] for r in linhas} == {"sem_entrada"}
        assert {(r["evdev_do_jogo"], r["hidraw_de_vpad"]) for r in linhas} == {(0, 4)}, (
            "a linha tem de dizer o que o jogo segura: nenhum evdev, os quatro vpads"
        )

    def test_quem_mexe_sai_do_estado_calado_e_volta_dizendo(self, bancada: Bancada) -> None:
        bancada.mundo.abrir_o_jogo_do_ge()
        bancada.volta()
        bancada.vigiar()
        bancada.mexer(P1)
        with structlog.testing.capture_logs() as registros:
            bancada.vigiar()
        assert _linhas(registros) == [], "sair do estado anômalo não loga"
        bancada.mundo.fechar_o_jogo()
        bancada.volta()
        with structlog.testing.capture_logs() as registros:
            bancada.vigiar()
            bancada.vigiar()
        motivos = {r["uniq"]: r["motivo"] for r in _linhas(registros)}
        # O P1 voltou ao estado; os outros três mudaram de motivo. Uma linha cada.
        assert motivos == {u: "sem_jogo" for u in MESA}
        assert len(_linhas(registros)) == len(MESA)

    def test_o_repouso_nao_loga(self, bancada: Bancada) -> None:
        """Endpoint sem stream é o repouso de todo controle fora de jogo."""
        bancada.endpoint_toca = {u: False for u in MESA}
        bancada.volta()
        with structlog.testing.capture_logs() as registros:
            bancada.vigiar()
        assert _linhas(registros) == []

    def test_o_endereco_sai_mascarado(self, mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> None:
        """Octetos 4 e 5 zerados, como o diário da bateria já faz.

        MORDIDA: logue o ``uniq`` cru.
        """
        bancada = Bancada(mundo, monkeypatch)
        bancada.controles = [
            ControleNaLista(uniq="aa:bb:cc:12:34:05", caminho="/dev/hidraw19", transporte="rádio")
        ]
        bancada.endpoint_toca = {"aa:bb:cc:12:34:05": True}
        bancada.volta()
        with structlog.testing.capture_logs() as registros:
            bancada.vigiar()
        assert [r["uniq"] for r in _linhas(registros)] == ["aa:bb:cc:00:00:05"]
        assert _linhas(registros)[0]["motivo"] == "sem_jogo"


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
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
        from hefesto_dualsense4unix.testing import FakeController

        monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
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
        assert daemon.store.counter("poll.tick") >= 5, "o laço não tiquetaqueou"
        assert daemon._quem_mexe.quem_joga() == {colada(P1)}  # type: ignore[attr-defined]
        assert len(chamadas) == daemon.store.counter("poll.tick"), "um snapshot por tique"


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
