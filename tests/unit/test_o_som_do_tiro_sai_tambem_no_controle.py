"""O som do tiro sai também no controle (O-SOM-DO-TIRO-SAI-TAMBEM-NO-CONTROLE-01).

O detector recorta o estalo do som do jogo (de 30 a 80 ms, fim em silêncio); o
motor do tato vivo leva o recorte ao controle de quem atirou; o alto-falante o
toca no nó de som daquele controle, com o volume que ele já escolheu, e cede
no rádio sem fatia livre; o tocador cala quando o jogo toca no nó. Tudo por
dublê: PCM sintético (semente fixa), relógio injetado, um cano de verdade no
lugar do processo de som, e o servidor de som de mentira.
"""
from __future__ import annotations

import math
import os
import random
import struct
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

TAXA = tj.TAXA
P1 = "aa:bb:cc:00:00:61"
P2 = "aa:bb:cc:00:00:62"
P3 = "aa:bb:cc:00:00:63"
P4 = "aa:bb:cc:00:00:64"
QUATRO = (P1, P2, P3, P4)
BYTES_POR_SEGUNDO = TAXA * tj.CANAIS * 2


def _som(segundos: float, nivel: float = 0.02, semente: int = 5) -> list[list[float]]:
    sorteio = random.Random(semente)
    return [
        [sorteio.gauss(0, nivel), sorteio.gauss(0, nivel)]
        for _ in range(int(segundos * TAXA))
    ]


def _estalo(quadros: list[list[float]], em_s: float, dura_s: float, forca: float = 0.7) -> None:
    """Um estalo que decai em ``dura_s``; com ``dura_s`` longo, um som que não acaba."""
    sorteio = random.Random(13)
    inicio = int(em_s * TAXA)
    duracao = int(dura_s * TAXA)
    for k in range(min(duracao, len(quadros) - inicio)):
        amostra = sorteio.uniform(-1, 1) * forca * math.exp(-3 * k / duracao)
        quadros[inicio + k][0] += amostra
        quadros[inicio + k][1] += amostra


def _pcm(quadros: list[list[float]]) -> bytes:
    planos = [max(-32767, min(32767, int(v * 32767))) for q in quadros for v in q]
    return struct.pack(f"<{len(planos)}h", *planos)


def _ouvir(pcm: bytes, pedaco: int, detector: tj.DetectorDeTransiente) -> list[tj.Transiente]:
    achados: list[tj.Transiente] = []
    for i in range(0, len(pcm), pedaco):
        parte = pcm[i:i + pedaco]
        achados += detector.ouvir(parte, (i + len(parte)) / BYTES_POR_SEGUNDO)
    return achados


def _um_recorte(dura_s: float, pedaco: int = tj.BYTES_POR_JANELA * 4) -> tj.Recorte:
    quadros = _som(0.6)
    _estalo(quadros, 0.3, dura_s)
    achados = _ouvir(_pcm(quadros), pedaco, tj.DetectorDeTransiente(recortar=True))
    assert len(achados) == 1
    recorte = achados[0].recorte
    assert recorte is not None and recorte.pronto
    return recorte


def _ultimo_quadro(pcm: bytes) -> tuple[int, int]:
    return struct.unpack("<2h", pcm[-4:])


def test_o_som_que_nao_acaba_e_cortado_em_80_ms_e_termina_em_silencio() -> None:
    recorte = _um_recorte(dura_s=0.4)
    assert recorte.duracao_s == pytest.approx(tj.RECORTE_MAXIMO_S)
    assert _ultimo_quadro(recorte.pcm) == (0, 0)


def test_o_estalo_curto_fecha_quando_cai_sem_passar_do_minimo() -> None:
    recorte = _um_recorte(dura_s=0.004)
    assert tj.RECORTE_MINIMO_S <= recorte.duracao_s < tj.RECORTE_MAXIMO_S
    assert _ultimo_quadro(recorte.pcm) == (0, 0)


def test_o_recorte_traz_o_proprio_estalo_e_nao_o_fundo() -> None:
    recorte = _um_recorte(dura_s=0.02)
    amostras = struct.unpack(f"<{len(recorte.pcm) // 2}h", recorte.pcm)
    assert max(abs(a) for a in amostras[:200]) > 0.3 * 32767


def test_o_pedaco_torto_do_cano_da_o_mesmo_recorte() -> None:
    reto = _um_recorte(dura_s=0.05)
    torto = _um_recorte(dura_s=0.05, pedaco=1234)
    assert torto.pcm == reto.pcm


def test_sem_pedido_de_recorte_o_estalo_vem_sem_ele() -> None:
    quadros = _som(0.6)
    _estalo(quadros, 0.3, 0.02)
    achados = _ouvir(_pcm(quadros), tj.BYTES_POR_JANELA * 4, tj.DetectorDeTransiente())
    assert [a.recorte for a in achados] == [None]


def test_o_fluxo_que_acaba_no_meio_fecha_o_recorte_em_silencio() -> None:
    quadros = _som(0.32)
    _estalo(quadros, 0.3, 0.4)
    detector = tj.DetectorDeTransiente(recortar=True)
    achados = _ouvir(_pcm(quadros), tj.BYTES_POR_JANELA, detector)
    recorte = achados[0].recorte
    assert recorte is not None and not recorte.pronto
    detector.fechar_o_recorte()
    assert recorte.pronto and recorte.duracao_s <= tj.RECORTE_MAXIMO_S
    assert _ultimo_quadro(recorte.pcm) == (0, 0)


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Servidor:
    """O servidor de som de mentira: a resposta de «o jogo toca no nó?» e quantas vezes."""

    def __init__(self, resposta: bool | None = False) -> None:
        self.resposta = resposta
        self.perguntas = 0

    def __call__(self, sink: str, rotulo: str) -> bool | None:
        self.perguntas += 1
        return self.resposta


def _nenhum_processo(*_a: Any, **_k: Any) -> Any:
    raise AssertionError("a régua das decisões não abre processo de som")


def _tocador(servidor: _Servidor, relogio: _Relogio | None = None) -> tj.TocadorDoEstalo:
    """Parado antes do primeiro estalo: sem fio, as decisões se leem bloco a bloco aqui."""
    tocador = tj.TocadorDoEstalo(
        "hefesto_som_APARELHOTESTE",
        o_jogo_toca=servidor,
        argv_de=lambda _s, _r: [],
        lancar=_nenhum_processo,
        conferir=lambda _r: None,
        relogio=relogio or _Relogio(),
    )
    tocador.parar()
    return tocador


def _drenar(tocador: tj.TocadorDoEstalo, blocos: int = 12) -> bytes:
    return b"".join(tocador.proximo_bloco() for _ in range(blocos))


def test_o_estalo_toca_inteiro_e_depois_vem_silencio() -> None:
    recorte = _um_recorte(dura_s=0.4)
    tocador = _tocador(_Servidor(False))
    tocador.tocar(recorte)
    saida = _drenar(tocador)
    assert saida.startswith(recorte.pcm)
    assert saida[len(recorte.pcm):] == bytes(len(saida) - len(recorte.pcm))
    assert tocador.contadores["tocados"] == 1


@pytest.mark.parametrize("resposta", [True, None], ids=["o-jogo-toca", "nao-sei"])
def test_com_o_jogo_tocando_no_no_o_estalo_cala(resposta: bool | None) -> None:
    tocador = _tocador(_Servidor(resposta))
    tocador.tocar(_um_recorte(dura_s=0.02))
    assert _drenar(tocador) == bytes(12 * tj.BYTES_DO_BLOCO)
    assert tocador.contadores == {
        "pedidos": 1, "tocados": 0, "calados_pelo_jogo": 1, "atrasados": 0,
    }


def test_o_recorte_que_nao_fecha_no_prazo_nao_toca() -> None:
    relogio = _Relogio()
    tocador = _tocador(_Servidor(False), relogio)
    aberto = tj.Recorte(relogio.agora)
    tocador.tocar(aberto)
    assert tocador.proximo_bloco() == bytes(tj.BYTES_DO_BLOCO)
    relogio.agora += tj.PRAZO_DO_RECORTE_S + 0.01
    tocador.proximo_bloco()
    aberto.acrescentar(b"\x10\x00" * (tj.BYTES_POR_JANELA // 2), 0.5)
    aberto.fechar()
    assert _drenar(tocador) == bytes(12 * tj.BYTES_DO_BLOCO)
    assert tocador.contadores["atrasados"] == 1 and not tocador.em_curso


def test_a_guarda_do_jogo_pergunta_uma_vez_por_segundo() -> None:
    relogio = _Relogio()
    servidor = _Servidor(False)
    tocador = _tocador(servidor, relogio)
    for _ in range(5):
        tocador.tocar(_um_recorte(dura_s=0.02))
        _drenar(tocador)
        relogio.agora += 0.1
    assert servidor.perguntas == 1
    relogio.agora += tj.VALIDADE_DA_GUARDA_S
    tocador.tocar(_um_recorte(dura_s=0.02))
    _drenar(tocador)
    assert servidor.perguntas == 2


class _ProcDeMentira:
    """O processo de som de mentira: lê o cano até fechar, e anota tudo o que chegou.

    Lê no passo de um tocador de verdade, um cano por vez: sem o passo, o laço de
    escrita do silêncio e o de leitura giram soltos e, com a máquina carregada,
    deixam a conferência do destino sem vez por mais que o prazo do teste.
    """

    def __init__(self) -> None:
        leitura, escrita = os.pipe()
        self.stdin = os.fdopen(escrita, "wb", buffering=0)
        self._leitura = leitura
        self.recebido = bytearray()
        self._morto = threading.Event()
        self._fechado = False
        self._fio = threading.Thread(target=self._ler, daemon=True)
        self._fio.start()

    def _ler(self) -> None:
        while True:
            try:
                pedaco = os.read(self._leitura, 4096)
            except OSError:
                break
            if not pedaco:
                break
            self.recebido += pedaco
            time.sleep(0.005)
        self._morto.set()

    def poll(self) -> int | None:
        return 0 if self._morto.is_set() else None

    def kill(self) -> None:
        self.stdin.close()

    def wait(self, timeout: float | None = None) -> int:
        self._morto.wait(timeout)
        if not self._fechado:
            self._fechado = True
            os.close(self._leitura)
        return 0


class _Lancador:
    def __init__(self) -> None:
        self.argvs: list[list[str]] = []
        self.procs: list[_ProcDeMentira] = []

    def __call__(self, argv: list[str], **_k: Any) -> _ProcDeMentira:
        self.argvs.append(list(argv))
        proc = _ProcDeMentira()
        self.procs.append(proc)
        return proc


def _esperar(condicao: Any, prazo_s: float = 3.0) -> bool:
    fim = time.monotonic() + prazo_s
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return condicao()


def test_o_tocador_de_pe_entrega_o_estalo_ao_no_e_sai_depois_da_folga() -> None:
    lancar = _Lancador()
    sink = "hefesto_som_APARELHOTESTE"
    tocador = tj.TocadorDoEstalo(
        sink,
        o_jogo_toca=_Servidor(False),
        argv_de=lambda s, r: ["tocador-de-mentira", s, r],
        lancar=lancar,
        conferir=lambda _r: sink,
        folga_s=0.3,
    )
    recorte = _um_recorte(dura_s=0.4)
    try:
        tocador.tocar(recorte)
        assert _esperar(lambda: lancar.procs and recorte.pcm in bytes(lancar.procs[0].recebido))
        assert lancar.argvs == [["tocador-de-mentira", sink, tj.rotulo_do_estalo(sink)]]
        assert _esperar(lambda: tocador._proc is None), "sem tiro, o tocador sai depois da folga"
    finally:
        tocador.parar()


def test_o_tocador_ligado_a_outro_no_morre_e_fica_recusado() -> None:
    lancar = _Lancador()
    tocador = tj.TocadorDoEstalo(
        "hefesto_som_APARELHOTESTE",
        o_jogo_toca=_Servidor(False),
        argv_de=lambda s, r: ["tocador-de-mentira"],
        lancar=lancar,
        conferir=lambda _r: "a_caixa_da_sala",
        folga_s=5.0,
    )
    try:
        tocador.tocar(_um_recorte(dura_s=0.02))
        assert _esperar(lambda: tocador._recusado_ate > time.monotonic())
        assert _esperar(lambda: tocador._proc is None)
        tocador.tocar(_um_recorte(dura_s=0.02))
        time.sleep(0.2)
        assert len(lancar.procs) == 1, "recusado, o tocador não sobe de novo"
    finally:
        tocador.parar()


def _so(*binarios: str) -> Any:
    return lambda nome: f"/usr/bin/{nome}" if nome in binarios else None


def test_o_comando_mira_o_no_do_controle_e_nunca_cai_na_saida_padrao() -> None:
    sink, rotulo = "hefesto_som_APARELHOTESTE", "hefesto-tato-estalo-x"
    pw = tj.argv_do_estalo(sink, rotulo, serial=77, achar=_so("pw-cat", "pacat"))
    assert pw[0] == "pw-cat" and "--target=77" in pw and "--channels=2" in pw
    propriedades = pw[pw.index("-P") + 1]
    for p in ("node.dont-fallback=true", "node.dont-reconnect=true",
              f"node.name={rotulo}", "state.restore-target=false"):
        assert p in propriedades
    pa = tj.argv_do_estalo(sink, rotulo, serial=None, achar=_so("pw-cat", "pacat"))
    assert pa[0] == "pacat" and f"--device={sink}" in pa
    assert "--property=node.dont-fallback=true" in pa
    assert tj.argv_do_estalo(sink, rotulo, serial=None, achar=_so("pw-cat")) == []


def _no(indice: int, nome: str) -> Any:
    return SimpleNamespace(indice=indice, nome=nome)


def _fluxo(alvo: int, nome: str) -> Any:
    return SimpleNamespace(alvo=str(alvo), propriedades={"node.name": nome})


def test_a_guarda_ve_o_jogo_no_no_e_nao_conta_o_proprio_estalo() -> None:
    sink, rotulo = "hefesto_som_APARELHOTESTE", "hefesto-tato-estalo-x"
    nos = [_no(40, sink), _no(41, "a_caixa_da_sala")]
    assert not tj.outro_fluxo_no_no(nos, [_fluxo(40, rotulo), _fluxo(41, "jogo")], sink, rotulo)
    assert tj.outro_fluxo_no_no(nos, [_fluxo(40, rotulo), _fluxo(40, "jogo")], sink, rotulo)


class _TocadorAnotando:
    def __init__(self) -> None:
        self.recortes: list[Any] = []

    def tocar(self, recorte: Any) -> None:
        self.recortes.append(recorte)


class _Som:
    """O subsistema de produção com os nós de mentira e o tocador anotando por nó."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, com_no: tuple[str, ...]) -> None:
        self.sub = AltoFalanteSubsystem(gerenciador=SimpleNamespace())
        self.sub._gerenciador = SimpleNamespace(nos={u.replace(":", ""): object() for u in com_no})
        self.tocadores: dict[str, _TocadorAnotando] = {}
        monkeypatch.setattr(self.sub, "_tocador_do_estalo", self._tocador)

    def _tocador(self, sink: str) -> _TocadorAnotando:
        return self.tocadores.setdefault(sink, _TocadorAnotando())

    def tocados(self) -> dict[str, int]:
        return {s: len(t.recortes) for s, t in self.tocadores.items() if t.recortes}


def test_cada_controle_toca_o_estalo_no_proprio_no(monkeypatch: pytest.MonkeyPatch) -> None:
    som = _Som(monkeypatch, QUATRO)
    for uniq in QUATRO:
        assert som.sub.tocar_o_estalo(uniq, tj.Recorte(0.0))
    assert som.tocados() == {nome_do_sink(u.replace(":", "")): 1 for u in QUATRO}


def test_sem_no_de_som_o_estalo_nao_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    som = _Som(monkeypatch, (P1,))
    assert not som.sub.tocar_o_estalo(P2, tj.Recorte(0.0))
    assert som.tocados() == {}


def test_no_radio_com_a_vaga_recusada_o_estalo_cede(monkeypatch: pytest.MonkeyPatch) -> None:
    som = _Som(monkeypatch, (P1, P2))
    som.sub._esperando_vaga = frozenset({(P1.replace(":", ""), "som")})
    assert not som.sub.tocar_o_estalo(P1, tj.Recorte(0.0))
    assert som.sub.tocar_o_estalo(P2, tj.Recorte(0.0))
    assert som.tocados() == {nome_do_sink(P2.replace(":", "")): 1}


def test_no_radio_com_a_ponte_cedendo_o_estalo_cede(monkeypatch: pytest.MonkeyPatch) -> None:
    som = _Som(monkeypatch, (P1,))
    chave = P1.replace(":", "")
    vaga = SimpleNamespace(cedendo=True)
    som.sub._pontes[chave] = object()
    som.sub._vaga_da_ponte = {chave: vaga}
    assert not som.sub.tocar_o_estalo(P1, tj.Recorte(0.0))
    vaga.cedendo = False
    assert som.sub.tocar_o_estalo(P1, tj.Recorte(0.0))
    assert som.tocados() == {nome_do_sink(chave): 1}


class _Ouvido:
    def __init__(self) -> None:
        self.estalos: list[tj.Transiente] = []
        self.ouvindo = True
        self.comecou = 0

    def comecar(self) -> None:
        self.comecou += 1

    def tirar(self) -> list[tj.Transiente]:
        estalos, self.estalos = self.estalos, []
        return estalos


class _Pad:
    def __init__(self) -> None:
        self.backend = "uhid"
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = True


class _Leitor:
    def __init__(self) -> None:
        self.r2_raw = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(l2_raw=0, r2_raw=self.r2_raw)


class _AltoFalante:
    def __init__(self) -> None:
        self.estalos: list[tuple[str, Any]] = []
        self.toques: list[str] = []

    def tocar_o_estalo(self, uniq: str, recorte: Any) -> bool:
        self.estalos.append((uniq, recorte))
        return True

    def tocar_o_toque(self, uniq: str, energia: float, lado: str, duracao_ms: int) -> bool:
        self.toques.append(uniq)
        return True


class _Mesa:
    """O daemon de mentira com o motor de produção: P1 e o co-op de P2 a P4."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, jogadores: tuple[str, ...], receita: tv.Receita
    ) -> None:
        monkeypatch.setattr(tv, "receita_ativa", lambda _d: receita)
        self.leitores = {uniq: _Leitor() for uniq in jogadores[1:]}
        self.pads = {uniq: _Pad() for uniq in jogadores}
        self.alto_falante = _AltoFalante()
        self.daemon = SimpleNamespace(
            controller=SimpleNamespace(primary_uniq=jogadores[0]),
            _last_state=SimpleNamespace(l2_raw=0, r2_raw=0),
            _gamepad_device=self.pads[jogadores[0]],
            _coop_manager=SimpleNamespace(
                _players={
                    uniq: SimpleNamespace(vpad=self.pads[uniq], reader=leitor)
                    for uniq, leitor in self.leitores.items()
                }
            ),
            _alto_falante_subsystem=self.alto_falante,
            display_authority="game",
        )
        self.motor = tv.TatoVivo(tv.atuadores_de_producao(self.daemon))
        self.daemon._tato_vivo = self.motor
        self.ouvido = _Ouvido()
        self.motor.ouvido = self.ouvido
        self.passo = tv.Passo(self.daemon, self.motor)
        self.agora = 0.0
        self.passo(self.agora)

    def gatilho(self, uniq: str, valor: int) -> None:
        if uniq == self.daemon.controller.primary_uniq:
            self.daemon._last_state = SimpleNamespace(l2_raw=0, r2_raw=valor)
        else:
            self.leitores[uniq].r2_raw = valor

    def tique(self, segundos: float = tv.INTERVALO_S) -> None:
        self.agora += segundos
        self.passo(self.agora)

    def estalo(self, atraso_s: float = 0.08) -> tj.Recorte:
        recorte = tj.Recorte(self.agora + atraso_s)
        self.ouvido.estalos.append(
            tj.Transiente(self.agora + atraso_s, "centro", 0.8, recorte)
        )
        self.tique(atraso_s)
        return recorte


_NO_CONTROLE = tv.Receita(som_no_controle=True)


def test_com_um_controle_o_recorte_vai_ao_alto_falante_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, (P1,), _NO_CONTROLE)
    recorte = mesa.estalo()
    assert mesa.alto_falante.estalos == [(P1, recorte)]
    assert mesa.ouvido.comecou >= 1, "a receita do som no controle sobe o ouvido"
    assert mesa.alto_falante.toques == [], "sem o lado do som, o estalo não vira toque"


def test_com_quatro_o_recorte_vai_so_a_quem_atirou(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, QUATRO, _NO_CONTROLE)
    mesa.estalo()
    assert mesa.alto_falante.estalos == [], "sem disparo o estalo não tem dono"
    for uniq in (P2, P4):
        mesa.gatilho(uniq, 255)
        mesa.tique()
        mesa.gatilho(uniq, 0)
        mesa.estalo()
        mesa.tique(0.5)
    assert [u for u, _r in mesa.alto_falante.estalos] == [P2, P4]


def test_o_jogo_que_manda_audio_ao_controle_gera_zero_estalo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, (P1,), _NO_CONTROLE)
    mesa.pads[P1].visto_ha_s = {"audio_do_jogo": 0.1}
    mesa.estalo()
    assert mesa.alto_falante.estalos == []


def test_no_modo_nativo_o_recorte_nao_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, (P1,), _NO_CONTROLE)
    mesa.daemon._gamepad_device = None
    mesa.estalo()
    assert mesa.alto_falante.estalos == []


def test_nasce_desligado_sem_a_receita_nada_toca_nem_ouve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, (P1,), tv.Receita(vibracao_por_tiro=True))
    mesa.estalo()
    assert mesa.alto_falante.estalos == []
    assert mesa.ouvido.comecou == 0
    assert tv.Receita().som_no_controle is False


def test_o_lado_do_som_sem_o_som_no_controle_nao_toca_o_recorte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, (P1,), tv.Receita(lado_do_som=True))
    mesa.estalo()
    assert mesa.alto_falante.estalos == []
    assert mesa.alto_falante.toques == [P1]


def test_o_ouvido_recorta_so_quando_a_receita_pede_o_som_no_controle() -> None:
    pedido = {"recortar": False}
    ouvido = tj.OuvidoDoJogo(
        lambda: True,
        achar_o_fluxo=lambda: None,
        recortar=lambda: pedido["recortar"],
    )
    ouvido.uma_volta()
    assert ouvido.detector.recortar is False
    pedido["recortar"] = True
    ouvido.uma_volta()
    assert ouvido.detector.recortar is True
