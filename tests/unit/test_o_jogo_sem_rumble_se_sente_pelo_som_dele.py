"""O jogo sem rumble se sente pelo som dele (O-JOGO-SEM-RUMBLE-SE-SENTE-PELO-SOM-DELE-01).

A fonte do som acorda só no controle em que o jogo não vibra há 20 s, com a mão jogando, e cede
no primeiro rumble dele, no mesmo tique. O estalo vira o toque na forma do estilo; o grave, um
corpo discreto (metade do Som no corpo) nos estilos de golpe que vestem o corpo. Nenhum processo
de som sobe aqui: o ouvido, o pad e o alto-falante são de mentira, o motor é o de produção.
"""
from __future__ import annotations

import math
import struct
from array import array
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

P1 = "aa:bb:cc:00:00:01"
QUATRO = (P1, "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
_ACAO = "acao"  # (noqa-acento)


class _Ouvido:
    def __init__(self) -> None:
        self.estalos: list[tj.Transiente] = []
        self.ouvindo = True

    def comecar(self) -> None:
        return None

    def tirar(self) -> list[tj.Transiente]:
        estalos, self.estalos = self.estalos, []
        return estalos


class _PadXbox:
    """O pad ``uinput`` do modo Xbox, com os contadores que o jogo move."""

    def __init__(self) -> None:
        self.backend = "uinput"
        self.visto_ha_s: dict[str, float] = {}
        self.game_open = True
        self.ff_last_sent = (0, 0)
        self.ff_nao_nulo_count = 0


class _Leitor:
    def __init__(self) -> None:
        self.foto = SimpleNamespace(l2_raw=0, r2_raw=0, buttons_pressed=frozenset(),
                                    lx=128, ly=128, rx=128, ry=128)

    def snapshot(self) -> Any:
        return self.foto


class _AltoFalante:
    def __init__(self) -> None:
        self.toques: list[tuple[str, str, str]] = []
        self.corpos: list[tuple[str, float]] = []

    def tocar_o_toque(
        self, uniq: str, energia: float, lado: str, duracao_ms: int,
        forma: str = formas.TOQUE,
    ) -> bool:
        self.toques.append((uniq, lado, forma))
        return True

    def tocar_o_corpo(self, uniq: str, amostras: Any, lado: str = "centro") -> bool:
        self.corpos.append((uniq, max((abs(x) for x in amostras), default=0.0)))
        return True


class _Mesa:
    """O daemon de mentira com o motor de produção, num estilo do catálogo."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, estilo: str, jogadores: tuple[str, ...] = (P1,),
    ) -> None:
        receita = tv.receita_do_estilo(POR_CHAVE[estilo])
        monkeypatch.setattr(tv, "receita_ativa", lambda _d: receita)
        monkeypatch.setattr(tv, "estilo_ativo", lambda _d: estilo)
        monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: False)
        self.pads = {uniq: _PadXbox() for uniq in jogadores}
        self.leitores = {uniq: _Leitor() for uniq in jogadores[1:]}
        self.alto_falante = _AltoFalante()
        self.primeiro = SimpleNamespace(l2_raw=0, r2_raw=0, buttons_pressed=frozenset(),
                                        raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128)
        self.daemon = SimpleNamespace(
            controller=SimpleNamespace(primary_uniq=jogadores[0]),
            _last_state=self.primeiro,
            _gamepad_device=self.pads[jogadores[0]],
            _coop_manager=SimpleNamespace(_players={
                uniq: SimpleNamespace(vpad=self.pads[uniq], reader=leitor)
                for uniq, leitor in self.leitores.items()}),
            _alto_falante_subsystem=self.alto_falante,
            display_authority="game",
        )
        self.motor = tv.TatoVivo(tv.atuadores_de_producao(self.daemon))
        self.daemon._tato_vivo = self.motor
        self.ouvido = _Ouvido()
        self.motor.ouvido = self.ouvido
        self.passo = tv.Passo(self.daemon, self.motor)
        self.agora = 0.0
        self._lado = 1
        self.passo(self.agora)

    def mexer(self) -> None:
        """A mão anda: o analógico esquerdo vai de um lado ao outro, em todo controle."""
        self._lado = -self._lado
        x = 128 + 60 * self._lado
        self.primeiro.raw_lx = x
        for leitor in self.leitores.values():
            leitor.foto.lx = x

    def gatilho(self, uniq: str, valor: int) -> None:
        if uniq == self.daemon.controller.primary_uniq:
            self.primeiro.r2_raw = valor
        else:
            self.leitores[uniq].foto.r2_raw = valor

    def tique(self, segundos: float = tv.INTERVALO_S) -> None:
        self.agora += segundos
        self.passo(self.agora)

    def jogar(self, segundos: float, mao: bool = True) -> None:
        """Os segundos passam com a mão jogando (ou parada), um tique por segundo."""
        for _ in range(int(segundos)):
            if mao:
                self.mexer()
            self.tique(1.0)

    def estalo(self, lado: str = "direito") -> None:
        self.ouvido.estalos.append(tj.Transiente(self.agora, lado, 0.8))

    def grave(self) -> None:
        """Um pedaço de 40 ms de 60 Hz, que o ouvido entrega ao filtro do corpo."""
        n = round(0.04 * formas.TAXA)
        quadros = b"".join(
            struct.pack("<hh", v, v) for v in (
                round(20000 * math.sin(2 * math.pi * 60 * i / formas.TAXA)) for i in range(n)))
        self.passo.alimentar_o_corpo(quadros)


def test_vinte_segundos_sem_rumble_e_a_mao_viva_o_estalo_vira_toque_na_forma_do_estilo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, _ACAO)
    mesa.jogar(5)
    mesa.estalo()
    mesa.tique()
    assert mesa.alto_falante.toques == [], "antes dos 20 s sem rumble a fonte dorme"
    mesa.jogar(16)
    mesa.estalo("esquerdo")
    mesa.tique()
    assert mesa.alto_falante.toques == [(P1, "esquerdo", formas.IMPACTO)]
    assert P1 in mesa.motor.acordados_pelo_som


def test_com_a_mao_parada_o_estalo_nao_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, _ACAO)
    mesa.jogar(25, mao=False)
    mesa.estalo()
    mesa.tique()
    assert mesa.alto_falante.toques == []


def test_um_rumble_no_meio_cala_a_fonte_no_mesmo_tique_e_o_toque_e_o_do_rumble(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prova da D-2210-O-SOM-DO-JOGO-ACORDA-ONDE-O-JOGO-CALA."""
    mesa = _Mesa(monkeypatch, _ACAO)
    mesa.jogar(21)
    mesa.grave()
    mesa.tique()
    assert mesa.alto_falante.corpos, "acordada, o grave vira o corpo discreto"
    corpos = len(mesa.alto_falante.corpos)
    tv.anotar_o_rumble(mesa.daemon, P1, 0, 200, mesa.agora)
    mesa.estalo("direito")
    mesa.grave()
    mesa.tique()
    assert mesa.alto_falante.toques == [(P1, "esquerdo", formas.IMPACTO)], "o toque é o do rumble"
    assert len(mesa.alto_falante.corpos) == corpos, "o corpo cede no mesmo tique"
    assert P1 not in mesa.motor.acordados_pelo_som


def test_o_rumble_que_o_pad_conta_entre_dois_tiques_tambem_a_faz_ceder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O pulso curto que subiu e caiu entre dois tiques: o contador do pad o denuncia."""
    mesa = _Mesa(monkeypatch, _ACAO)
    mesa.jogar(21)
    mesa.pads[P1].ff_nao_nulo_count += 1
    mesa.estalo()
    mesa.tique()
    assert mesa.alto_falante.toques == []
    mesa.jogar(19)
    mesa.estalo()
    mesa.tique()
    assert mesa.alto_falante.toques == [], "a fonte volta só depois de 20 s calado de novo"
    mesa.jogar(2)
    mesa.estalo()
    mesa.tique()
    assert mesa.alto_falante.toques == [(P1, "direito", formas.IMPACTO)]


def test_nos_quatro_controles_o_rumble_de_um_so_cala_a_fonte_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, _ACAO, QUATRO)
    mesa.jogar(21)
    assert mesa.motor.acordados_pelo_som == frozenset(QUATRO)
    tv.anotar_o_rumble(mesa.daemon, QUATRO[1], 0, 180, mesa.agora)
    for uniq in QUATRO[:2]:
        mesa.gatilho(uniq, 255)
    mesa.tique()
    mesa.estalo()
    mesa.tique()
    tocados = [t for t in mesa.alto_falante.toques if t[1] == "direito"]
    assert tocados == [(QUATRO[0], "direito", formas.IMPACTO)]
    assert mesa.motor.acordados_pelo_som == frozenset(QUATRO) - {QUATRO[1]}


@pytest.mark.parametrize("estilo", ["retro", "nativo"])
def test_no_retro_e_no_nativo_o_mesmo_estalo_nao_toca_nada(
    monkeypatch: pytest.MonkeyPatch, estilo: str,
) -> None:
    mesa = _Mesa(monkeypatch, estilo)
    mesa.jogar(21)
    mesa.grave()
    mesa.estalo()
    mesa.tique()
    assert mesa.alto_falante.toques == []
    assert mesa.alto_falante.corpos == []
    assert mesa.motor.acordados_pelo_som == frozenset()


@pytest.mark.parametrize("estilo", ["retro", "point_and_click", "visual_novel", "maratona",
                                    "corrida", "simulacao"])
def test_a_receita_do_estilo_diz_quem_liga_a_fonte(estilo: str) -> None:
    assert not tv.receita_do_estilo(POR_CHAVE[estilo]).som_quando_o_jogo_cala
    acao = tv.receita_do_estilo(POR_CHAVE[_ACAO])
    assert acao.som_quando_o_jogo_cala and tv.pede_o_ouvido(acao)
    assert tv.Receita(som_quando_o_jogo_cala=True).ligada
    assert tv.Receita.de({"som_quando_o_jogo_cala": True}).som_quando_o_jogo_cala


@pytest.mark.parametrize(("estilo", "veste"), [
    ("terror", True), (_ACAO, True), ("souls", True), ("aventura", True),
    ("luta", False), ("esportes", False), ("fps", False), ("plataforma", False),
])
def test_o_grave_vira_corpo_discreto_so_nos_estilos_de_golpe_que_vestem_o_corpo(
    monkeypatch: pytest.MonkeyPatch, estilo: str, veste: bool,
) -> None:
    mesa = _Mesa(monkeypatch, estilo)
    mesa.jogar(21)
    mesa.grave()
    mesa.tique()
    assert bool(mesa.alto_falante.corpos) is veste


def test_o_corpo_discreto_e_a_metade_do_som_no_corpo(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, "terror")
    mesa.jogar(21)
    mesa.grave()
    mesa.tique()
    inteiro = _Mesa(monkeypatch, "corrida")
    inteiro.grave()
    inteiro.tique()
    (_, discreto), = mesa.alto_falante.corpos
    (_, cheio), = inteiro.alto_falante.corpos
    assert cheio > 0.05
    assert discreto == pytest.approx(cheio * tv.FORCA_DO_CORPO_DISCRETO, rel=1e-3)


def _pcm(segundos: float, nivel_de: Any) -> bytes:
    n = round(segundos * tj.TAXA)
    amostras = array("h")
    for i in range(n):
        v = round(32767 * nivel_de(i / tj.TAXA) * math.sin(2 * math.pi * 220 * i / tj.TAXA))
        amostras.extend((v, v))
    return amostras.tobytes()


def _estalos_do_pcm(pcm: bytes, inicio: float) -> list[tj.Transiente]:
    detector = tj.DetectorDeTransiente()
    achados: list[tj.Transiente] = []
    passo = tj.BYTES_POR_JANELA * 4
    for k in range(0, len(pcm), passo):
        achados.extend(detector.ouvir(pcm[k:k + passo], inicio + (k + passo) / (tj.TAXA * 4)))
    return achados


def test_a_musica_de_energia_constante_nao_vira_toque() -> None:
    assert _estalos_do_pcm(_pcm(3.0, lambda t: 0.5), 0.0) == []


def test_a_batida_rapida_da_musica_o_fundo_aprende_e_o_teto_segura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma batida de 20 por segundo: o limiar que se adapta a absorve em meio segundo; e mesmo
    uma rajada que passasse inteira (40 estalos em 2 s) não passa do teto do tato."""
    batida = _estalos_do_pcm(
        _pcm(2.0, lambda t: 0.6 if (t % 0.05) < 0.008 else 0.01), 0.0)
    assert 0 < len(batida) <= 6
    assert max(e.instante for e in batida) < 0.5, "depois de meio segundo a batida é fundo"
    mesa = _Mesa(monkeypatch, _ACAO)
    mesa.jogar(21)
    inicio = mesa.agora
    for k in range(40):
        mesa.ouvido.estalos.append(tj.Transiente(inicio + k * 0.05, "centro", 0.8))
    for _ in range(int(2.0 / tv.INTERVALO_S)):
        mesa.tique()
    assert 0 < len(mesa.alto_falante.toques) <= 2 * tv.TETO_POR_CONTROLE
