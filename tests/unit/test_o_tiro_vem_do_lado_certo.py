"""O tiro vem do lado certo (O-TIRO-VEM-DO-LADO-CERTO-01).

O detector de transiente acha o estalo do som do jogo e o lado de onde ele
vem; o motor do tato vivo leva o estalo ao controle de quem atirou, e o toque
sai do lado certo. Tudo por dublê: PCM sintético (semente fixa), um gravador
de mentira com ``stdout`` em memória, relógio injetado e o tocador anotando.
"""
from __future__ import annotations

import io
import math
import random
import struct
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj

TAXA = tj.TAXA
P1 = "aa:bb:cc:00:00:51"
P2 = "aa:bb:cc:00:00:52"
P3 = "aa:bb:cc:00:00:53"
P4 = "aa:bb:cc:00:00:54"
QUATRO = (P1, P2, P3, P4)


# --- O som sintético ----------------------------------------------------------


def _fundo(segundos: float, nivel: float = 0.03, semente: int = 7) -> list[list[float]]:
    sorteio = random.Random(semente)
    return [
        [sorteio.gauss(0, nivel), sorteio.gauss(0, nivel)]
        for _ in range(int(segundos * TAXA))
    ]


def _estalo(
    quadros: list[list[float]],
    em_s: float,
    esquerda: float,
    direita: float,
    *,
    forca: float = 0.7,
    semente: int = 11,
) -> None:
    """Um estalo de 4 ms que decai, com o ganho de cada canal (o som posicional)."""
    sorteio = random.Random(semente)
    inicio = int(em_s * TAXA)
    duracao = int(0.004 * TAXA)
    for k in range(duracao):
        amostra = sorteio.uniform(-1, 1) * forca * math.exp(-3 * k / duracao)
        quadros[inicio + k][0] += amostra * esquerda
        quadros[inicio + k][1] += amostra * direita


def _pcm(quadros: list[list[float]]) -> bytes:
    planos = [max(-32767, min(32767, int(v * 32767))) for q in quadros for v in q]
    return struct.pack(f"<{len(planos)}h", *planos)


def _ouvir(
    quadros: list[list[float]],
    detector: tj.DetectorDeTransiente | None = None,
    pedaco: int = tj.BYTES_POR_JANELA * 4,
) -> list[tj.Transiente]:
    det = detector or tj.DetectorDeTransiente()
    pcm = _pcm(quadros)
    achados: list[tj.Transiente] = []
    for i in range(0, len(pcm), pedaco):
        parte = pcm[i:i + pedaco]
        achados += det.ouvir(parte, (i + len(parte)) / (4 * TAXA))
    return achados


# --- O detector ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("ganhos", "lado"),
    [((1.0, 0.1), "esquerdo"), ((0.1, 1.0), "direito"), ((1.0, 1.0), "centro")],
)
def test_o_estalo_sai_do_lado_de_onde_vem(ganhos: tuple[float, float], lado: str) -> None:
    quadros = _fundo(2.0)
    _estalo(quadros, 1.0, *ganhos)
    achados = _ouvir(quadros)
    assert [a.lado for a in achados] == [lado]
    assert 1.0 <= achados[0].instante <= 1.0 + 2 * tj.JANELA_S
    assert 0.0 < achados[0].energia <= 1.0


@pytest.mark.parametrize("nivel", [0.0, 0.03, 0.2])
def test_o_fundo_constante_nao_dispara(nivel: float) -> None:
    assert _ouvir(_fundo(3.0, nivel)) == []


def test_a_rajada_de_20_estalos_por_segundo_da_20_eventos() -> None:
    quadros = _fundo(2.0)
    for k in range(20):
        _estalo(quadros, 0.5 + k * 0.05, 1.0, 1.0, semente=k)
    assert len(_ouvir(quadros)) == 20


def test_o_eco_do_mesmo_tiro_nao_dispara_de_novo() -> None:
    quadros = _fundo(2.0)
    _estalo(quadros, 1.0, 1.0, 1.0)
    _estalo(quadros, 1.016, 1.0, 1.0, forca=0.5, semente=12)
    assert len(_ouvir(quadros)) == 1


def test_o_som_alto_que_sobe_e_desce_devagar_nao_e_tiro() -> None:
    sorteio = random.Random(5)
    quadros: list[list[float]] = []
    for i in range(int(2.0 * TAXA)):
        t = i / TAXA
        nivel = 0.01 + 0.59 * (1 - math.cos(2 * math.pi * 4 * t)) / 2 if t > 0.3 else 0.01
        quadros.append([sorteio.gauss(0, nivel), sorteio.gauss(0, nivel)])
    # O primeiro crescendo depois do silêncio pode valer um; o resto é o fundo que se move.
    assert len(_ouvir(quadros)) <= 1


def test_o_pedaco_torto_do_cano_da_o_mesmo_resultado() -> None:
    quadros = _fundo(2.0)
    _estalo(quadros, 0.7, 1.0, 0.1)
    _estalo(quadros, 1.3, 0.1, 1.0, semente=3)
    retos = [(round(a.instante, 3), a.lado) for a in _ouvir(quadros)]
    tortos = [(a.lado) for a in _ouvir(quadros, pedaco=1001)]
    assert [lado for _i, lado in retos] == tortos == ["esquerdo", "direito"]


def test_a_cpu_do_detector_por_segundo_de_som() -> None:
    pcm = _pcm(_fundo(5.0, 0.25))
    detector = tj.DetectorDeTransiente()
    comeco = time.process_time()
    for i in range(0, len(pcm), tj.LEITURA):
        detector.ouvir(pcm[i:i + tj.LEITURA], i / (4 * TAXA))
    por_segundo = (time.process_time() - comeco) / 5.0
    print(f"cpu do detector: {por_segundo * 1000:.2f} ms por segundo de som")
    assert por_segundo < 0.05


# --- O fluxo do jogo e o gravador ----------------------------------------------


def _fluxo(indice: int, pid: int, nome: str, serial: int, corked: bool = False) -> Any:
    return SimpleNamespace(
        indice=indice,
        corked=corked,
        propriedades={
            "application.process.id": str(pid),
            "node.name": nome,
            "object.serial": str(serial),
        },
    )


def test_o_fluxo_e_o_do_processo_de_jogo_e_nunca_o_nosso() -> None:
    fluxos = [
        _fluxo(1, 100, "Firefox", 501),
        _fluxo(2, 200, "hefesto-tato-toque", 502),
        _fluxo(3, 200, "jogo-pausado", 503, corked=True),
        _fluxo(4, 200, "jogo", 504),
    ]
    achado = tj.fluxo_do_jogo(fluxos, {200})
    assert achado == tj.FluxoDoJogo(indice=4, serial=504, nome="jogo", pid=200)
    assert tj.fluxo_do_jogo(fluxos, set()) is None
    assert tj.fluxo_do_jogo(fluxos[:1], {200}) is None


def test_o_gravador_mira_o_fluxo_e_nao_cai_no_microfone() -> None:
    fluxo = tj.FluxoDoJogo(indice=4, serial=504, nome="jogo", pid=200)
    tudo = {"pw-record": "/usr/bin/pw-record", "parec": "/usr/bin/parec"}
    pw = tj.argv_do_ouvido(fluxo, pipewire=True, latencia_ms=40, achar=tudo.get)
    assert pw[0] == "pw-record" and "--target=504" in pw and "--format=s16" in pw
    assert any("node.dont-fallback=true" in parte for parte in pw)
    pa = tj.argv_do_ouvido(fluxo, pipewire=False, latencia_ms=40, achar=tudo.get)
    assert pa[0] == "parec" and "--monitor-stream=4" in pa
    assert "--property=node.dont-fallback=true" in pa
    assert tj.argv_do_ouvido(fluxo, pipewire=True, latencia_ms=40, achar=lambda _b: None) == []


class _Gravador:
    def __init__(self, pcm: bytes) -> None:
        self.stdout = io.BytesIO(pcm)
        self.argv: list[str] = []

    def poll(self) -> int | None:
        return None


class _Bancada:
    """O ouvido com tudo de mentira: o fluxo, o gravador, a conferência e o relógio."""

    def __init__(self, pcm: bytes, alvo: str | None = "jogo") -> None:
        self.quer = True
        self.fluxo: tj.FluxoDoJogo | None = tj.FluxoDoJogo(4, 504, "jogo", 200)
        self.abertos: list[list[str]] = []
        self.derrubados: list[Any] = []
        self.alvo = alvo
        self.agora = 10.0
        self.gravador = _Gravador(pcm)
        self.ouvido = tj.OuvidoDoJogo(
            lambda: self.quer,
            achar_o_fluxo=lambda: self.fluxo,
            montar_argv=lambda f: ["pw-record", f"--target={f.serial}"],
            abrir=self._abrir,
            derrubar=lambda proc, **_k: self.derrubados.append(proc),
            conferir_o_alvo=lambda _rotulo: self.alvo,
            relogio=lambda: self.agora,
        )

    def _abrir(self, argv: list[str]) -> _Gravador:
        self.abertos.append(argv)
        return self.gravador

    def esperar_o_leitor(self) -> None:
        leitor = self.ouvido._leitor
        assert leitor is not None
        leitor.join(timeout=5.0)


def _pcm_com_um_estalo_a_esquerda() -> bytes:
    quadros = _fundo(1.0)
    _estalo(quadros, 0.5, 1.0, 0.1)
    return _pcm(quadros)


def test_sem_pedido_o_ouvido_nao_grava_nada() -> None:
    bancada = _Bancada(b"")
    bancada.quer = False
    bancada.ouvido.uma_volta()
    assert bancada.abertos == []


def test_sem_fluxo_de_jogo_o_ouvido_fica_calado() -> None:
    bancada = _Bancada(b"")
    bancada.fluxo = None
    bancada.ouvido.uma_volta()
    assert bancada.abertos == [] and not bancada.ouvido.ouvindo


def test_o_ouvido_grava_o_jogo_e_entrega_o_estalo_com_o_lado() -> None:
    bancada = _Bancada(_pcm_com_um_estalo_a_esquerda())
    bancada.ouvido.uma_volta()
    assert bancada.abertos == [["pw-record", "--target=504"]]
    bancada.esperar_o_leitor()
    assert bancada.ouvido.ouvindo
    assert [t.lado for t in bancada.ouvido.tirar()] == ["esquerdo"]
    assert bancada.ouvido.tirar() == []
    bancada.agora += tj.VIVO_S + 0.1
    assert not bancada.ouvido.ouvindo, "sem PCM chegando o ouvido não está ouvindo"


def test_o_gravador_que_ligou_em_outro_no_cai() -> None:
    bancada = _Bancada(b"", alvo="microfone")
    bancada.ouvido.uma_volta()
    bancada.ouvido.uma_volta()
    assert bancada.derrubados == [bancada.gravador]
    assert bancada.ouvido.contadores["alvo_errado"] == 1


def test_nao_sei_o_alvo_nao_derruba() -> None:
    bancada = _Bancada(b"", alvo=None)
    bancada.ouvido.uma_volta()
    bancada.ouvido.uma_volta()
    assert bancada.derrubados == []


def test_o_pedido_que_acaba_cala_o_gravador() -> None:
    bancada = _Bancada(b"")
    bancada.ouvido.uma_volta()
    bancada.quer = False
    bancada.ouvido.uma_volta()
    assert bancada.derrubados == [bancada.gravador]


# --- O motor: o estalo vai a quem atirou, do lado certo -------------------------


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
        self.l2_raw = 0
        self.r2_raw = 0

    def snapshot(self) -> Any:
        return SimpleNamespace(l2_raw=self.l2_raw, r2_raw=self.r2_raw)


class _AltoFalante:
    def __init__(self) -> None:
        self.toques: list[tuple[str, str]] = []

    def tocar_o_toque(self, uniq: str, energia: float, lado: str, duracao_ms: int) -> bool:
        self.toques.append((uniq, lado))
        return True


class _Mesa:
    """O daemon de mentira com o motor de produção: P1 e o co-op de P2 a P4."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        jogadores: tuple[str, ...],
        receita: tv.Receita,
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

    def estalo(self, lado: str, atraso_s: float = 0.08) -> None:
        self.ouvido.estalos.append(tj.Transiente(self.agora + atraso_s, lado, 0.8))
        self.tique(atraso_s)


_DO_SOM = tv.Receita(lado_do_som=True)


def test_com_um_controle_o_estalo_e_dele_e_vem_do_lado_certo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, (P1,), _DO_SOM)
    mesa.estalo("esquerdo")
    mesa.tique(0.2)
    mesa.estalo("direito")
    assert mesa.alto_falante.toques == [(P1, "esquerdo"), (P1, "direito")]
    assert mesa.ouvido.comecou >= 1, "a receita do lado do som sobe o ouvido"


def test_com_quatro_o_estalo_vai_so_a_quem_atirou(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, QUATRO, _DO_SOM)
    mesa.estalo("direito")
    assert mesa.alto_falante.toques == [], "sem disparo o estalo não tem dono"
    for uniq in (P1, P3):
        mesa.gatilho(uniq, 255)
        mesa.tique()
        mesa.gatilho(uniq, 0)
        mesa.estalo("esquerdo")
        mesa.tique(0.5)
    assert mesa.alto_falante.toques == [(P1, "esquerdo"), (P3, "esquerdo")]


def test_a_arma_automatica_segura_o_gatilho_e_cada_estalo_e_de_quem_segura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, QUATRO, _DO_SOM)
    mesa.gatilho(P4, 255)
    mesa.tique()
    for _ in range(3):
        mesa.tique(0.4)
        mesa.estalo("direito")
    assert mesa.alto_falante.toques == [(P4, "direito")] * 3


def test_um_tiro_da_um_toque_com_o_ouvido_no_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    receita = tv.Receita(vibracao_por_tiro=True, lado_do_som=True)
    mesa = _Mesa(monkeypatch, (P1,), receita)
    tv.anotar_o_rumble(mesa.daemon, P1, 0, 200, mesa.agora)
    mesa.estalo("esquerdo")
    assert mesa.alto_falante.toques == [(P1, "esquerdo")]
    # Sem o som do jogo chegando, o toque volta a vir do rumble.
    mesa.ouvido.ouvindo = False
    mesa.tique(0.5)
    tv.anotar_o_rumble(mesa.daemon, P1, 0, 0, mesa.agora)
    tv.anotar_o_rumble(mesa.daemon, P1, 0, 200, mesa.agora)
    mesa.tique()
    assert mesa.alto_falante.toques == [(P1, "esquerdo"), (P1, "esquerdo")]


def test_o_jogo_que_manda_a_haptica_gera_zero_toque(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, (P1,), _DO_SOM)
    mesa.pads[P1].visto_ha_s = {"audio_do_jogo": 0.1}
    mesa.estalo("esquerdo")
    assert mesa.alto_falante.toques == []


def test_no_modo_nativo_o_estalo_nao_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, (P1,), _DO_SOM)
    mesa.daemon._gamepad_device = None
    mesa.estalo("esquerdo")
    assert mesa.alto_falante.toques == []


def test_sem_a_receita_do_lado_o_estalo_nao_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, (P1,), tv.Receita(vibracao_por_tiro=True))
    mesa.estalo("esquerdo")
    assert mesa.alto_falante.toques == []
    assert mesa.ouvido.comecou == 0, "sem o lado do som o ouvido não sobe"
