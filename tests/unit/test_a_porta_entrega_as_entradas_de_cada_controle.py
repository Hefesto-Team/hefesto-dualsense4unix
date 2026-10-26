"""O tópico ``entradas``: os analógicos, os gatilhos e o touchpad de CADA controle (24/10/2026).

A sprint A-PORTA-ENTREGA-OS-EIXOS-OS-GATILHOS-E-O-TOUCHPAD-DE-CADA-CONTROLE-01. Antes dela a
extensão só recebia botão: o gatilho chegava como o ``l2``/``r2`` digital, o touchpad como as
três regiões de clique, e o ``estado`` era o do controle do posto só. Aqui:

1. cada controle da mesa (P1 a P4, cabo e rádio, pelo co-op ou pelo leitor passivo do hub) sai
   com o ``uniq``, o ``jogador`` e o ``transporte`` dele;
2. os dedos saem de 0 a 1 pela área do touchpad, e o dedo que levanta sai como ``dedos: []``;
3. sem quem assine, nenhum leitor é consultado;
4. o eixo parado não sai, o ritmo nunca passa de 30 por segundo e o último valor sempre chega;
5. no Modo Nativo o tique segue congelado, e as entradas saem igual.

Os dublês são os do aparelho (o leitor do hub, o do toque, o co-op e o backend sem E/S); a porta,
o socket, o ``SensorHub`` e o laço do serviço são os de verdade.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import select
import socket
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.core.evdev_reader import EvdevSnapshot, PontoDeToque, TouchState
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.mods.manifesto import (
    NOME_DAS_ENTRADAS,
    TOPICOS_DE_LEITURA,
    o_que_a_permissao_deixa,
    permissao_valida,
)
from hefesto_dualsense4unix.mods.porta import (
    ENTRADAS_POR_SEGUNDO,
    Porta,
    entradas_de_todo_controle_no_servico,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import curto  # noqa: F401

UNIQS = ("aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004")
P1, P2, P3, P4 = UNIQS

MESAS = {
    "mista": ("usb", "bt", "usb", "bt"),
    "tres-adaptadores-e-um-cabo": ("bt", "bt", "bt", "usb"),
    "todos-no-cabo": ("usb", "usb", "usb", "usb"),
    "todos-no-bt": ("bt", "bt", "bt", "bt"),
    "um-so-no-cabo": ("usb",),
    "um-so-no-bt": ("bt",),
}
FONTES = ("coop", "hub")

TIQUE = 1.0 / 120


class _Extensao:
    """A extensão de mentira: fala a porta por um socket e lê os eventos linha a linha.

    Lê do socket cru, com o próprio buffer: o ``makefile`` que vence o prazo uma vez não lê
    mais nada (``cannot read from timed out object``), e a régua do ritmo drena várias vezes.
    """

    def __init__(self, caminho: pathlib.Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.buffer = b""
        self.proximo = 0
        self.eventos: list[dict[str, Any]] = []

    def _linha(self, segundos: float | None) -> dict[str, Any] | None:
        while b"\n" not in self.buffer:
            pronto, _, _ = select.select([self.sock], [], [], segundos)
            if not pronto:
                return None
            pedaco = self.sock.recv(65536)
            if not pedaco:
                return None
            self.buffer += pedaco
        linha, self.buffer = self.buffer.split(b"\n", 1)
        resposta: dict[str, Any] = json.loads(linha)
        return resposta

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta = self._linha(5.0)
            assert resposta is not None, f"a porta não respondeu {metodo}"
            if resposta.get("id") == self.proximo:
                return resposta
            self.eventos.append(resposta)

    def esperar_evento(self, segundos: float) -> dict[str, Any] | None:
        if self.eventos:
            return self.eventos.pop(0)
        return self._linha(segundos)

    def fechar(self) -> None:
        self.sock.close()


class _Relogio:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


class _LeitorDoHub:
    """O leitor passivo do ``SensorHub``: devolve o snapshot de agora, como o ``EvdevReader``."""

    def __init__(self) -> None:
        self.snap = EvdevSnapshot()

    def snapshot(self) -> EvdevSnapshot:
        return self.snap

    def stop(self) -> None:
        """Nada a parar no dublê."""


class _LeitorDoToque:
    """O leitor do touchpad do hub: o ``TouchState`` de agora, com os pontos de cada slot."""

    def __init__(self) -> None:
        self.estado = TouchState()

    def touch_state(self) -> TouchState:
        return self.estado

    def stop(self) -> None:
        """Nada a parar no dublê."""


class _Backend:
    """O que o backend responde sem E/S: quem está na mesa, por onde, e quem é o posto."""

    def __init__(self, uniqs: tuple[str, ...], vias: tuple[str, ...]) -> None:
        self.primary_uniq = uniqs[0]
        self._alvos = {f"chave-{n}": u for n, u in enumerate(uniqs)}
        self._vias = {f"chave-{n}": v for n, v in enumerate(vias)}

    def alvos_conectados(self) -> dict[str, str]:
        return dict(self._alvos)

    def transportes_dos_alvos(self) -> dict[str, str]:
        return dict(self._vias)


class _Coop:
    """O co-op com os jogadores de pé: o leitor de cada um segura o nó (``live_snapshots``)."""

    def __init__(self, uniqs: tuple[str, ...]) -> None:
        self.snaps = {u: EvdevSnapshot() for u in uniqs}
        self._numeros = {u: n + 2 for n, u in enumerate(uniqs)}

    def live_snapshots(self) -> dict[str, EvdevSnapshot]:
        return dict(self.snaps)

    def numeros_de_jogador(self) -> dict[str, int]:
        return dict(self._numeros)


class _Mesa:
    """A mesa de ``vias``: o P1 é o posto, os outros vêm da ``fonte``; o hub é o de verdade."""

    def __init__(self, porta: Porta, vias: tuple[str, ...], fonte: str) -> None:
        self.uniqs = UNIQS[: len(vias)]
        self.vias = dict(zip(self.uniqs, vias, strict=True))
        self.hub = SensorHub(auto_manutencao=False)
        self.toques = {u: _LeitorDoToque() for u in self.uniqs}
        self.hub._touch.update(self.toques)
        outros = self.uniqs[1:]
        self.coop = _Coop(outros if fonte == "coop" else ())
        self.passivos = {u: _LeitorDoHub() for u in outros} if fonte == "hub" else {}
        self.hub._gamepad.update(self.passivos)
        numeros = {u: n + 1 for n, u in enumerate(self.uniqs)}
        self.daemon = SimpleNamespace(
            controller=_Backend(self.uniqs, vias),
            _coop_manager=self.coop,
            _mods_supervisor=SimpleNamespace(porta=porta),
            _garantir_sensor_hub=lambda: self.hub,
            identity_registry=SimpleNamespace(
                numero_da_lampada=lambda uniq, assign=False: numeros.get(uniq)),
        )
        self.posto = ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                                     transport="bt" if vias[0] == "bt" else "usb")

    def mexer(self, uniq: str, **eixos: int) -> None:
        """``uniq`` mexe os ``eixos`` (``lx``… ``l2``, ``r2``), de 0 a 255."""
        if uniq == self.uniqs[0]:
            nomes = {"lx": "raw_lx", "ly": "raw_ly", "rx": "raw_rx", "ry": "raw_ry",
                     "l2": "l2_raw", "r2": "r2_raw"}
            self.posto = ControllerState(**{**vars(self.posto),
                                            **{nomes[k]: v for k, v in eixos.items()}})
            return
        campos = {("l2_raw" if k == "l2" else "r2_raw" if k == "r2" else k): v
                  for k, v in eixos.items()}
        if uniq in self.coop.snaps:
            self.coop.snaps[uniq] = EvdevSnapshot(**{**vars(self.coop.snaps[uniq]), **campos})
        else:
            leitor = self.passivos[uniq]
            leitor.snap = EvdevSnapshot(**{**vars(leitor.snap), **campos})

    def tocar(self, uniq: str, *pontos: tuple[int, int]) -> None:
        self.toques[uniq].estado = TouchState(
            touching=bool(pontos), x=pontos[0][0] if pontos else 0,
            y=pontos[0][1] if pontos else 0,
            pontos=tuple(PontoDeToque(slot=n, x=x, y=y, identidade=n + 1)
                         for n, (x, y) in enumerate(pontos)))

    def tique(self, relogio: _Relogio, segundos: float = 0.05) -> None:
        relogio.t += segundos
        entradas_de_todo_controle_no_servico(self.daemon, self.posto)


async def _porta(pasta: pathlib.Path, relogio: _Relogio) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(pasta / "mods.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1,
                  relogio=relogio)
    await porta.iniciar()
    porta.registrar("ficha", "exemplo", os.getpid(), ["ler:entradas", "ler:botoes"])
    return porta


async def _entrar(pasta: pathlib.Path, topicos: list[str]) -> _Extensao:
    ext = _Extensao(pasta / "mods.sock")
    await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
    assinou = await asyncio.to_thread(ext.pedir, "eventos.assinar", {"topicos": topicos})
    assert "result" in assinou, assinou
    return ext


def _drenar(ext: _Extensao, espera: float = 0.3) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    while (evento := ext.esperar_evento(espera)) is not None:
        saida.append(evento["params"])
    return saida


def _sem_o_que_nao_e_entrada(eventos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assert all(e["topico"] == "entradas" and e["nome"] == NOME_DAS_ENTRADAS for e in eventos)
    return [e["dados"] for e in eventos]


def test_o_topico_e_a_permissao_existem_e_dizem_o_que_entregam() -> None:
    assert TOPICOS_DE_LEITURA["entradas"] == (NOME_DAS_ENTRADAS,)
    assert permissao_valida("ler:entradas")
    assert "touchpad" in o_que_a_permissao_deixa("ler:entradas")
    assert "jogador 1" in o_que_a_permissao_deixa("ler:estado"), (
        "o estado é o do controle do posto: a frase não promete os quatro")


@pytest.mark.parametrize("fonte", FONTES)
@pytest.mark.parametrize("mesa", list(MESAS))
def test_cada_controle_sai_com_o_uniq_o_jogador_e_o_transporte_dele(
    curto: pathlib.Path, mesa: str, fonte: str,  # noqa: F811
) -> None:
    """Cada controle aperta o R2 e mexe o analógico, e solta: um evento de ida e um de volta."""
    relogio = _Relogio()

    async def corrida() -> tuple[_Mesa, list[dict[str, Any]]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS[mesa], fonte)
        ext = await _entrar(curto, ["entradas"])
        try:
            bancada.tique(relogio)
            for uniq in bancada.uniqs:
                bancada.mexer(uniq, r2=200, lx=30)
                bancada.tique(relogio)
                bancada.mexer(uniq, r2=0, lx=128)
                bancada.tique(relogio)
            return bancada, _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    bancada, dados = asyncio.run(corrida())
    visto = [(d["uniq"], d["jogador"], d["transporte"], d["r2"], d["lx"]) for d in dados]
    esperado = [
        (uniq, n + 1, bancada.vias[uniq], r2, lx)
        for n, uniq in enumerate(bancada.uniqs)
        for r2, lx in ((200, 30), (0, 128))
    ]
    assert visto == esperado, f"{mesa}/{fonte}: {visto}"
    assert all(d["dedos"] == [] and d["l2"] == 0 and (d["ly"], d["rx"], d["ry"]) == (128,) * 3
               for d in dados)


@pytest.mark.parametrize("mesa", ["mista", "um-so-no-bt"])
def test_o_dedo_sai_normalizado_e_o_levantar_sai_como_nenhum_dedo(
    curto: pathlib.Path, mesa: str,  # noqa: F811
) -> None:
    relogio = _Relogio()

    async def corrida() -> tuple[_Mesa, list[dict[str, Any]]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS[mesa], "hub")
        ext = await _entrar(curto, ["entradas"])
        try:
            for uniq in bancada.uniqs:
                bancada.tocar(uniq, (960, 540))
                bancada.tique(relogio)
                bancada.tocar(uniq, (1919, 0), (0, 1079))
                bancada.tique(relogio)
                bancada.tocar(uniq)
                bancada.tique(relogio)
            return bancada, _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    bancada, dados = asyncio.run(corrida())
    um, dois = [{"x": 0.5, "y": 0.5}], [{"x": 1.0, "y": 0.0}, {"x": 0.0, "y": 1.0}]
    esperado = [(uniq, dedos) for uniq in bancada.uniqs for dedos in (um, dois, [])]
    assert [(d["uniq"], d["dedos"]) for d in dados] == esperado


def test_o_dedo_vem_da_leitura_que_so_ve_e_nunca_do_toque_que_segura_o_no(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """O ``toque_da_peca`` pede o nó (EVIOCGRAB) e tiraria o touchpad do cursor do computador."""
    relogio = _Relogio()

    async def corrida() -> SensorHub:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"], "hub")
        ext = await _entrar(curto, ["entradas"])
        try:
            bancada.tocar(P2, (900, 500))
            bancada.tique(relogio)
            await asyncio.to_thread(_drenar, ext)
            return bancada.hub
        finally:
            ext.fechar()
            await porta.parar()

    hub = asyncio.run(corrida())
    assert hub._demanda_do_toque == {}, "a porta pediu o nó do touchpad"
    assert hub._demanda == {}, "a leitura do dedo segurou o leitor de movimento e o de toque"


def test_sem_assinante_nenhum_leitor_e_consultado(
    curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    lidos: list[Any] = []

    def _leu(*argumentos: Any) -> dict[str, Any]:
        lidos.append(argumentos)
        return {}

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.entradas_de_cada_controle", _leu)
    relogio = _Relogio()

    async def corrida() -> _Mesa:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"], "hub")
        ext = await _entrar(curto, ["botoes"])
        try:
            bancada.mexer(P2, r2=200)
            bancada.tique(relogio)
            return bancada
        finally:
            ext.fechar()
            await porta.parar()

    bancada = asyncio.run(corrida())
    assert lidos == []
    assert bancada.hub._demanda == {} and bancada.hub._demanda_entradas == {}


def test_o_eixo_parado_nao_sai_o_ritmo_tem_teto_e_o_ultimo_valor_chega(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    """200 tiques com o analógico tremendo no centro: nada. Dois segundos subindo o gatilho
    a 120 Hz: no máximo 30 por segundo, e a volta ao zero chega."""
    relogio = _Relogio()

    async def corrida() -> tuple[list[dict[str, Any]], list[tuple[float, dict[str, Any]]]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"], "hub")
        ext = await _entrar(curto, ["entradas"])
        try:
            for n in range(200):
                bancada.mexer(P1, lx=127 + n % 3, ry=129 - n % 2)
                bancada.mexer(P2, rx=126 + n % 3)
                bancada.tique(relogio, TIQUE)
            parado = _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext, 0.2))
            instantes: list[tuple[float, dict[str, Any]]] = []
            for n in range(240):
                bancada.mexer(P2, r2=min(254, n + 3))
                bancada.tique(relogio, TIQUE)
                for dados in _sem_o_que_nao_e_entrada(
                        await asyncio.to_thread(_drenar, ext, 0.002)):
                    instantes.append((relogio.t, dados))
            bancada.mexer(P2, r2=0)
            for _ in range(6):
                bancada.tique(relogio, TIQUE)
            instantes += [(relogio.t, d) for d in
                          _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext))]
            return parado, instantes
        finally:
            ext.fechar()
            await porta.parar()

    parado, instantes = asyncio.run(corrida())
    assert parado == [], f"o analógico parado saiu: {parado}"
    tempos = [t for t, _ in instantes]
    pior = max(sum(1 for t in tempos if inicio <= t < inicio + 1.0) for inicio in tempos)
    assert pior <= ENTRADAS_POR_SEGUNDO, f"{pior} num segundo"
    assert pior >= ENTRADAS_POR_SEGUNDO - 10, f"o teto segurou demais: {pior} num segundo"
    assert instantes[-1][1]["r2"] == 0, "a volta do gatilho ao zero não chegou"
    assert all(d["uniq"] == P2 for _, d in instantes)


def test_o_controle_que_sai_com_o_gatilho_apertado_sai_em_repouso(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    relogio = _Relogio()

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"], "hub")
        ext = await _entrar(curto, ["entradas"])
        try:
            bancada.mexer(P3, r2=255)
            bancada.tique(relogio)
            del bancada.daemon.controller._alvos["chave-2"]
            bancada.tique(relogio)
            bancada.tique(relogio)
            return _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    visto = [(d["uniq"], d["jogador"], d["transporte"], d["r2"]) for d in asyncio.run(corrida())]
    assert visto == [(P3, 3, "usb", 255), (P3, 3, "usb", 0)]


@pytest.mark.parametrize("quem", [P1, P2])
def test_a_queda_leva_o_repouso_mesmo_sem_tique(curto: pathlib.Path, quem: str) -> None:  # noqa: F811
    """A mesa que cai inteira não tem tique: o ``controller.disconnected`` leva o repouso."""
    relogio = _Relogio()

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"], "hub")
        ext = await _entrar(curto, ["entradas"])
        try:
            bancada.mexer(quem, l2=255, ry=0)
            bancada.tique(relogio)
            porta.bus.publish(EventTopic.CONTROLLER_DISCONNECTED,
                              {"reason": "alvo_sumiu", "uniq": quem})
            await asyncio.sleep(0.05)
            porta.bus.publish(EventTopic.CONTROLLER_DISCONNECTED,
                              {"reason": "alvo_sumiu", "uniq": quem})
            return _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    visto = [(d["uniq"], d["l2"], d["ry"]) for d in asyncio.run(corrida())]
    assert visto == [(quem, 255, 0), (quem, 0, 128)]


def test_quem_assina_depois_recebe_o_gatilho_que_ja_estava_apertado(
    curto: pathlib.Path,  # noqa: F811
) -> None:
    relogio = _Relogio()

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"], "hub")
        bancada.mexer(P2, l2=90)
        bancada.tique(relogio)
        ext = await _entrar(curto, ["entradas"])
        try:
            bancada.tique(relogio)
            bancada.tique(relogio)
            return _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext))
        finally:
            ext.fechar()
            await porta.parar()

    assert [(d["uniq"], d["l2"]) for d in asyncio.run(corrida())] == [(P2, 90)]


@pytest.mark.asyncio
async def test_no_modo_nativo_o_gatilho_do_posto_e_o_do_hub_passivo_ainda_saem(
    curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    """O ``_poll_loop`` de verdade, com o tique congelado do Nativo: as entradas saem.

    Prova da D-2410-A-PORTA-ENTREGA-AS-ENTRADAS-DE-CADA-CONTROLE-EM-TODO-MODO.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle._a_fabrica_do_supervisor",
                        lambda: lambda daemon: None)
    hub = SensorHub(auto_manutencao=False)
    passivo = _LeitorDoHub()
    hub._gamepad[P2] = passivo
    monkeypatch.setattr(Daemon, "_garantir_sensor_hub", lambda self: hub)
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.subsystems.poll._na_mesa",
                        lambda controller: [P2])
    repouso = ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                              transport="bt")
    controle = FakeController(transport="bt", states=[repouso])
    relogio = _Relogio()
    porta = await _porta(curto, relogio)
    ext = await _entrar(curto, ["entradas"])
    daemon = Daemon(controller=controle, bus=EventBus(), store=StateStore(), config=DaemonConfig(
        poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False))

    async def _nada() -> None:
        return None

    daemon._mods_supervisor = SimpleNamespace(porta=porta, parar=_nada)
    rodando = asyncio.create_task(daemon.run())
    laco = asyncio.get_running_loop()
    try:
        prazo = laco.time() + 5.0
        while controle._idx < 1 and laco.time() < prazo:
            await asyncio.sleep(0.02)
        daemon._native_mode = True
        antes = daemon.store.counter("input.settling.tick")
        controle._states, controle._idx = [ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=200, connected=True, transport="bt")], 0
        passivo.snap = EvdevSnapshot(r2_raw=150)
        while daemon.store.counter("input.settling.tick") < antes + 5 and laco.time() < prazo:
            relogio.t += 0.1
            await asyncio.sleep(0.02)
    finally:
        daemon.stop()
        await rodando
    dados = _sem_o_que_nao_e_entrada(await asyncio.to_thread(_drenar, ext))
    ext.fechar()
    await porta.parar()
    assert daemon.store.counter("input.settling.tick") >= antes + 5, "o tique não congelou"
    visto = {(d["uniq"], d["r2"]) for d in dados}
    assert {(None, 200), (P2, 150)} <= visto, f"no Nativo as entradas não saíram: {dados}"
