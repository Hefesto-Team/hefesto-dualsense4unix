"""O-SOM-QUE-O-JOGO-MANDA-AO-CONTROLE-TOCA-TAMBEM-PELO-RADIO-01 — a frente do endpoint toca.

**A causa, lida no código em 13/10/2026:** o endpoint de quatro canais do
aparelho carrega duas coisas. Os canais 3-4 são os motores, e a bomba do
``0x36`` os levava ao bloco da háptica. Os canais 1-2, a frente, são o som que
o jogo manda ao controle, e NADA os levava ao rádio: o ouvido só contava os
traseiros, e a bomba só lia o nó do alto-falante. Pelo cabo o som da frente
toca; pelo rádio ficava mudo.

**A cura:** a frente de cada bloco (512 quadros a 48 kHz) é reamostrada para os
480 quadros a 45 kHz do som e somada, com saturação, ao PCM do alto-falante
antes do Opus. Ela é som, não vibração: não passa pelo ganho nem pelo portão da
vibração. A decisão da ponte conta a frente com sinal como «som».

Sem aparelho: o PCM é de mentira, o hidraw é um cano. Endereços da faixa
forjada ``aa:bb:cc``.
"""

from __future__ import annotations

import struct
from array import array
from collections.abc import Callable
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import haptica_bt as hb
from tests.unit.test_a_haptica_por_audio_e_o_alto_falante_chegam_ao_radio import (  # noqa: F401
    FORJA,
    P1,
    Mesa,
    no_do,
    sala,
)

PICO = 20000


def _quadros(canais: tuple[int, int, int, int], vezes: int = af.QUADROS_POR_BLOCO_HAPTICO) -> bytes:
    """``vezes`` quadros de quatro canais s16le com os valores dados."""
    return struct.pack("<4h", *canais) * vezes


FRENTE = _quadros((PICO, -PICO, 0, 0))
MOTORES = _quadros((0, 0, PICO, -PICO))
AMBOS = _quadros((PICO, -PICO, PICO, -PICO))
MUDO = _quadros((0, 0, 0, 0))


def _amostras(pcm: bytes) -> array[int]:
    saida: array[int] = array("h")
    saida.frombytes(pcm)
    return saida


class _Grava:
    """O Opus de mentira: guarda o PCM que recebeu, que é o que vai ao alto-falante."""

    def __init__(self) -> None:
        self.recebidos: list[bytes] = []

    def codificar(self, pcm: bytes) -> bytes:
        self.recebidos.append(bytes(pcm))
        return b"\x01" * int(af.BYTES_POR_QUADRO_OPUS)


def _fonte(blocos: list[bytes]) -> Callable[[int], bytes]:
    fila = list(blocos)

    def _ler(_quantos: int) -> bytes:
        return fila.pop(0) if fila else b""

    return _ler


def _bomba(
    endpoint: list[bytes],
    *,
    monitor: bytes | None = None,
    ganho: float = 1.0,
    leva: bool = True,
) -> tuple[Any, _Grava]:
    grava = _Grava()
    mudo = bytes(af.BYTES_DE_PCM_POR_QUADRO)
    bomba = af.BombaDeSomPeloRadio(
        fonte=lambda _n: monitor if monitor is not None else mudo,
        fonte_haptica=_fonte(endpoint),
        escritor=lambda r: len(r),
        seco=False,
        codificador=grava,
        so_com_sinal=True,
        ganho_da_haptica=ganho,
        leva_a_haptica=leva,
    )
    return bomba, grava


class TestAFrenteVai48Para45:
    def test_as_taxas_batem_com_as_do_rádio(self) -> None:
        assert hb.QUADROS_DA_FRENTE_NO_SOM == af.AMOSTRAS_POR_QUADRO
        assert hb.QUADROS_POR_BLOCO == af.QUADROS_POR_BLOCO_HAPTICO

    def test_o_nivel_constante_sai_constante_nos_480_quadros(self) -> None:
        esq = array("h", [PICO] * hb.QUADROS_POR_BLOCO)
        dir_ = array("h", [-PICO] * hb.QUADROS_POR_BLOCO)
        saida = _amostras(hb.frente_reamostrada(esq, dir_))
        assert len(saida) == 2 * af.AMOSTRAS_POR_QUADRO
        assert set(saida[0::2]) == {PICO} and set(saida[1::2]) == {-PICO}

    def test_a_rampa_continua_rampa_e_a_interpolacao_e_linear(self) -> None:
        """Rampa de 15 por quadro: o quadro i de saída está em 16/15·i e vale 16·i."""
        rampa = array("h", range(0, 512 * 15, 15))
        saida = _amostras(hb.frente_reamostrada(rampa, array("h", [0] * 512)))
        esq = list(saida[0::2])
        assert all(abs(valor - 16 * i) <= 1 for i, valor in enumerate(esq)), (
            "a frente não foi interpolada linearmente de 512 para 480 quadros"
        )
        assert set(saida[1::2]) == {0}, "o canal direito mudo ganhou sinal"

    def test_silencio_exato_nao_custa_nem_soma(self) -> None:
        zeros = array("h", [0] * hb.QUADROS_POR_BLOCO)
        assert hb.frente_reamostrada(zeros, zeros) == b""
        base = struct.pack("<2h", 5, 6) * 10
        assert hb.somar_com_saturacao(base, b"") is base

    def test_a_soma_satura_nos_dois_lados(self) -> None:
        base = struct.pack("<4h", 30000, -30000, 100, -100)
        outro = struct.pack("<4h", 30000, -30000, 5, -5)
        assert _amostras(hb.somar_com_saturacao(base, outro)) == array(
            "h", [32767, -32768, 105, -105]
        )

    def test_tamanho_diferente_nao_soma_nada(self) -> None:
        base = struct.pack("<2h", 1, 2)
        assert hb.somar_com_saturacao(base, base * 2) is base


class TestOSeparadorAlinhaAosBlocos:
    def test_pedacos_de_tamanho_qualquer_fecham_uma_frente_por_bloco(self) -> None:
        sep = hb.SeparadorDaFrente()
        pcm = FRENTE * 2
        saidas: list[bytes] = []
        for i in range(0, len(pcm), 1001):  # 1001 B: nunca cai na fronteira do quadro
            saidas.extend(sep.alimentar(pcm[i : i + 1001]))
        assert len(saidas) == 2
        assert all(len(f) == af.BYTES_DE_PCM_POR_QUADRO for f in saidas)

    def test_o_conversor_e_o_separador_fecham_o_mesmo_numero_de_blocos(self) -> None:
        conversor, sep = hb.ConversorDeHaptica(), hb.SeparadorDaFrente()
        pcm = AMBOS * 3
        blocos = frentes = 0
        for i in range(0, len(pcm), 777):
            blocos += len(conversor.alimentar(pcm[i : i + 777]))
            frentes += len(sep.alimentar(pcm[i : i + 777]))
        assert blocos == frentes == 3

    def test_so_os_motores_dao_frente_muda(self) -> None:
        assert hb.SeparadorDaFrente().alimentar(MOTORES) == [b""]

    def test_o_sinal_da_frente_nao_olha_os_motores(self) -> None:
        assert hb.tem_sinal_na_frente(FRENTE) is True
        assert hb.tem_sinal_na_frente(MOTORES) is False
        assert hb.tem_sinal_na_frente(MUDO) is False
        assert hb.tem_sinal_na_frente(AMBOS) is True


class TestABombaSomaAFrenteAoAltoFalante:
    def test_so_a_frente_toca_e_nao_vibra(self) -> None:
        bomba, grava = _bomba([FRENTE] * 3)
        bomba.rodar(segundos=10)
        assert bomba.contagem.quadros_opus == 3, "o som da frente não foi ao bloco de som"
        assert bomba.contagem.hapticos_no_fio == 0, "a frente virou vibração"
        pcm = _amostras(grava.recebidos[0])
        assert set(pcm[0::2]) == {PICO} and set(pcm[1::2]) == {-PICO}

    def test_so_os_traseiros_vibram_e_nao_tocam(self) -> None:
        bomba, grava = _bomba([MOTORES] * 3)
        bomba.rodar(segundos=10)
        assert bomba.contagem.hapticos_no_fio == 3
        assert bomba.contagem.quadros_opus == 0 and grava.recebidos == []

    def test_frente_e_traseiros_juntos_tocam_e_vibram(self) -> None:
        bomba, _grava = _bomba([AMBOS] * 3)
        bomba.rodar(segundos=10)
        assert bomba.contagem.quadros_opus == 3 and bomba.contagem.hapticos_no_fio == 3
        assert bomba.contagem.quadros_com_frente == 3

    def test_a_vibracao_em_zero_ainda_toca_a_frente(self) -> None:
        """Ganho 0 e portão fechado calam os motores; a frente é som e segue."""
        bomba, grava = _bomba([AMBOS] * 3, ganho=0.0, leva=False)
        bomba.rodar(segundos=10)
        assert bomba.contagem.hapticos_no_fio == 0, "a vibração em 0 vibrou"
        assert bomba.contagem.quadros_opus == 3, "a vibração em 0 calou o som da frente"
        pcm = _amostras(grava.recebidos[0])
        assert max(pcm) == PICO, "o ganho da vibração escalou a frente"

    def test_a_frente_soma_ao_som_do_alto_falante_e_satura(self) -> None:
        voz = struct.pack("<2h", 12000, -12000) * af.AMOSTRAS_POR_QUADRO
        grande = _quadros((25000, -25000, 0, 0))
        bomba, grava = _bomba([grande], monitor=voz)
        bomba.rodar(segundos=10)
        pcm = _amostras(grava.recebidos[0])
        assert set(pcm[0::2]) == {32767}, "12000 + 25000 devia saturar em +32767"
        assert set(pcm[1::2]) == {-32768}

    def test_a_frente_com_a_voz_menor_soma_sem_saturar(self) -> None:
        voz = struct.pack("<2h", 1000, -1000) * af.AMOSTRAS_POR_QUADRO
        bomba, grava = _bomba([FRENTE], monitor=voz)
        bomba.rodar(segundos=10)
        pcm = _amostras(grava.recebidos[0])
        assert set(pcm[0::2]) == {1000 + PICO} and set(pcm[1::2]) == {-1000 - PICO}

    def test_a_frente_muda_nao_mexe_na_voz(self) -> None:
        voz = struct.pack("<2h", 700, -700) * af.AMOSTRAS_POR_QUADRO
        bomba, grava = _bomba([MOTORES, MOTORES], monitor=voz)
        bomba.rodar(segundos=10)
        assert grava.recebidos and all(p == voz for p in grava.recebidos)
        assert bomba.contagem.quadros_com_frente == 0

    def test_a_frente_seguinte_nao_herda_a_anterior(self) -> None:
        bomba, _grava = _bomba([FRENTE, MUDO, MUDO, MUDO])
        bomba.rodar(segundos=10)
        assert bomba.contagem.quadros_com_frente == 1


class TestOOuvidoSabeDaFrente:
    @pytest.fixture
    def ouvido(self, monkeypatch: pytest.MonkeyPatch) -> af.OuvidoDosNos:
        novo = af.OuvidoDosNos()
        monkeypatch.setattr(af, "OUVIDO", novo)
        return novo

    def test_a_frente_acende_a_chave_dela_e_nao_a_dos_motores(self, ouvido: Any) -> None:
        ler = af.fonte_que_ouve(_fonte([FRENTE]), "endpoint::x", canais=af.CANAIS_DA_HAPTICA)
        assert ler(len(FRENTE))
        assert ouvido.tem_sinal(af.no_da_frente("endpoint::x")) is True
        assert ouvido.tem_sinal("endpoint::x") is False, "a frente acendeu os motores"

    def test_os_motores_acendem_a_chave_deles_e_nao_a_da_frente(self, ouvido: Any) -> None:
        ler = af.fonte_que_ouve(_fonte([MOTORES]), "endpoint::x", canais=af.CANAIS_DA_HAPTICA)
        assert ler(len(MOTORES))
        assert ouvido.tem_sinal("endpoint::x") is True
        assert ouvido.tem_sinal(af.no_da_frente("endpoint::x")) is False

    def test_o_no_de_dois_canais_nao_ganha_chave_de_frente(self, ouvido: Any) -> None:
        voz = struct.pack("<2h", 9, 9) * 100
        ler = af.fonte_que_ouve(_fonte([voz]), "hefesto_som_x")
        assert ler(len(voz))
        assert ouvido.tem_sinal(af.no_da_frente("hefesto_som_x")) is None


def _ganho_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon import ganho_da_haptica as dono
    from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod

    class _Zero(dono.GanhoDaHaptica):  # type: ignore[misc]
        def pct(self, uniq: str | None) -> int:
            return 0

        def fator(self, uniq: str | None) -> float:
            return 0.0

    monkeypatch.setattr(mod, "GANHO", _Zero())


class TestADecisaoDaPonteContaAFrenteComoSom:
    def test_frente_com_sinal_e_o_alto_falante_calado_sobe_a_ponte_de_som(
        self, sala: Mesa, monkeypatch: pytest.MonkeyPatch  # noqa: F811
    ) -> None:
        """Só o endpoint aberto, a vibração em 0, a frente com sinal: a ponte é «som»."""
        _ganho_zero(monkeypatch)
        endpoint = no_do(P1)
        sala.fonte(endpoint).quadro = FRENTE[:8]
        sala.servidor.tocar(endpoint, FORJA)
        sala.volta()
        sala.esperar(af.no_da_frente(endpoint), True)
        sala.volta()
        assert sala.leva(P1) is False, "a vibração em 0 não devia levar a háptica"
        assert sala.sub._modo_da_ponte.get(P1) == "som", "a frente não contou como som"
        sala.esperar_o_fio(P1, som=True, haptica=False)

    def test_endpoint_so_com_motores_e_a_vibracao_em_zero_nao_sobe_ponte(
        self, sala: Mesa, monkeypatch: pytest.MonkeyPatch  # noqa: F811
    ) -> None:
        _ganho_zero(monkeypatch)
        endpoint = no_do(P1)
        sala.fonte(endpoint).quadro = MOTORES[:8]
        sala.servidor.tocar(endpoint, FORJA)
        sala.volta()
        sala.esperar(endpoint, True)
        sala.volta()
        assert P1 not in sala.sub._pontes, "motor com a vibração em 0 subiu ponte"

    def test_a_frente_com_a_vibracao_ligada_vai_junto_com_a_haptica(
        self, sala: Mesa  # noqa: F811
    ) -> None:
        endpoint = no_do(P1)
        sala.fonte(endpoint).quadro = AMBOS[:8]
        sala.abrir_a_sala(P1)
        sala.volta()
        sala.esperar_o_fio(P1, som=True, haptica=True)
