"""RUMBLE-PRESO-01 — o motor não pode girar para sempre quando o stop se perde.

O relato que abriu isto, em 25/07/2026, com o jogo aberto: *"ao jogar, ele muda
e o rumble fica totalmente quebrado, tremendo sem parar — em todo jogo, em
qualquer DualSense"*.

A cadeia, reproduzida em laboratório antes de qualquer linha de conserto:

1. o jogo liga a vibração num report COM os bits de vibração — o vpad encaminha
   ao controle físico e o motor gira;
2. o jogo manda qualquer report SEM esses bits (lightbar, gatilho, mic — o que
   um jogo com gatilhos adaptativos faz o tempo todo);
3. o gate de `_VIBRATION_FLAGS` sai cedo, sem tocar no estado de vibração. O
   gate está CERTO: os bytes de motor desses reports vêm zerados e encaminhá-los
   matava a vibração em curso, defeito que ele existe para curar;
4. o pedido de parada, se vier num report assim, nunca é visto;
5. e não fica um pulso pendurado: o `report_thread` do backend reafirma
   `rumble_asserted` em TODO report que monta, então o motor não desacelera.

Estes testes travam as duas metades. Nenhum deles conhece a implementação além
do contrato público (o vpad recebe eventos de output e chama `rumble_sink`), e o
relógio é injetado — nada aqui dorme.

Desde 03/11/2026 (O-RUMBLE-QUE-O-JOGO-SEGURA-NAO-EXPIRA-EM-TRES-SEGUNDOS-01) a rede
não é mais um teto de silêncio de 3 s, que cortava a vibração sustentada de um jogo
vivo: o motor só se solta quando ninguém mais lê o pad, por duas consultas seguidas.
A consulta aqui é um dublê que responde vivo ou morto.
"""
from __future__ import annotations

import contextlib
import os
import struct
import threading

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid


class _RelogioFalso:
    """Relógio monotônico controlado pelo teste (segundos)."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avanca(self, segundos: float) -> None:
        self.agora += segundos


class _VpadDeEnsaio(uhid.UhidDualSense):
    """Vpad com o fd desligado — exercita só o caminho de output/rumble."""

    def __init__(self, relogio: _RelogioFalso) -> None:
        self.recebido: list[tuple[int, int]] = []
        self.rumble_sink = lambda w, s: self.recebido.append((w, s))
        self.time_fn = relogio
        self.player = 1
        self._leitura, self._escrita = os.pipe()
        os.set_blocking(self._leitura, False)
        self._fd = self._leitura
        self._last_sent = (0, 0)
        self._lock = threading.RLock()
        self._rumble_count = 0
        self._output_count = 0
        self._rumble_parada_sdl_count = 0
        self._output_id_estranho_count = 0
        self._output_id_estranho_amostra = None
        self._rumble_anel = []
        self._visto_em = {}

    def fechar(self) -> None:
        for fd in (self._leitura, self._escrita):
            with contextlib.suppress(OSError):
                os.close(fd)

    def _replicate_from_output(self, body: bytes) -> None:
        """REPLICA-03 fora de escopo aqui: gatilho/lightbar têm testes próprios."""

    def _flush_replicas(self) -> None:
        """Idem."""

    def bombeia(self) -> None:
        """Um tique do poll loop DE VERDADE — passa pelo `pump_ff` público."""
        self.pump_ff()
        consulta = self._leitor_consulta
        if consulta is not None:
            consulta.join(5.0)


class _LeitorDeEnsaio:
    """O dublê da consulta «o jogo ainda lê este pad?»."""

    def __init__(self) -> None:
        self.vivo: bool | None = True
        self.chamadas = 0

    def __call__(self, _pad: object) -> tuple[bool | None, str]:
        self.chamadas += 1
        return self.vivo, "dublê"


def _evento_de_output(
    flag0: int, weak: int, strong: int, flag1: int = 0
) -> bytes:
    """Monta um UHID_OUTPUT real: 4B de tipo + data[4096] + size + rtype."""
    corpo = bytearray(48)
    corpo[uhid._VALID_FLAG0_OFFSET] = flag0
    corpo[uhid._VALID_FLAG1_OFFSET] = flag1
    corpo[uhid._RUMBLE_WEAK_OFFSET] = weak
    corpo[uhid._RUMBLE_STRONG_OFFSET] = strong
    report = bytes([uhid._OUTPUT_REPORT_USB]) + bytes(corpo)
    dados = bytearray(4 + uhid.HID_MAX_DESCRIPTOR_SIZE + 2 + 1)
    dados[4 : 4 + len(report)] = report
    struct.pack_into("<H", dados, 4 + uhid.HID_MAX_DESCRIPTOR_SIZE, len(report))
    return bytes(dados)


_COM_VIBRACAO = uhid._VIBRATION_FLAGS
_SO_LIGHTBAR = 0x04


@pytest.fixture
def leitor(monkeypatch: pytest.MonkeyPatch) -> _LeitorDeEnsaio:
    dublê = _LeitorDeEnsaio()
    monkeypatch.setattr(uhid, "CONSULTAR_O_LEITOR", dublê)
    return dublê


@pytest.fixture
def ensaio(leitor: _LeitorDeEnsaio):
    relogio = _RelogioFalso()
    vpad = _VpadDeEnsaio(relogio)
    try:
        yield vpad, relogio
    finally:
        vpad.fechar()


def test_stop_normal_do_jogo_continua_chegando(ensaio) -> None:
    """O caminho feliz não pode ser sacrificado pela rede de segurança."""
    vpad, _ = ensaio
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 0, 0))
    assert vpad.recebido == [(200, 200), (0, 0)]


def test_report_sem_bits_de_vibracao_nao_mata_a_vibracao_em_curso(ensaio) -> None:
    """O gate original: report de lightbar/gatilho NÃO zera o motor."""
    vpad, relogio = ensaio
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    for _ in range(50):
        relogio.avanca(0.05)
        vpad._handle_output(_evento_de_output(_SO_LIGHTBAR, 0, 0))
        vpad.bombeia()
    assert vpad.recebido == [(200, 200)], (
        "report sem bits de vibração não pode encaminhar motor zerado"
    )


def _ate_soltar(vpad, relogio) -> None:
    """As duas consultas seguidas sem leitor, e o passe que solta."""
    for _ in range(uhid._MORTO_POR_SEGUIDAS + 1):
        vpad.bombeia()
        relogio.avanca(uhid._CONFERE_O_LEITOR_S + 0.1)
    vpad.bombeia()


def test_o_jogo_que_morreu_sem_fechar_solta_o_motor(ensaio, leitor) -> None:
    """O stop se perde e o jogo morre segurando o nó: o motor não gira para sempre."""
    vpad, relogio = ensaio
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    assert vpad.recebido == [(200, 200)]
    leitor.vivo = False
    _ate_soltar(vpad, relogio)
    assert vpad.recebido == [(200, 200), (0, 0)], (
        "sem leitor por duas consultas, o motor preso tem de ser zerado"
    )


def test_a_soltura_nao_dispara_duas_vezes(ensaio, leitor) -> None:
    """Zerou uma vez, cala a boca: nada de enxurrada de (0,0) a cada tique."""
    vpad, relogio = ensaio
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 180, 180))
    leitor.vivo = False
    _ate_soltar(vpad, relogio)
    for _ in range(20):
        relogio.avanca(1.0)
        vpad.bombeia()
    assert vpad.recebido == [(180, 180), (0, 0)]


def test_jogo_que_reafirma_o_mesmo_valor_nao_e_cortado(ensaio) -> None:
    """Vibração longa e legítima sobrevive, e o mesmo par não se reenvia."""
    vpad, relogio = ensaio
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 120, 120))
    for _ in range(10):
        relogio.avanca(1.5)
        vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 120, 120))
        vpad.bombeia()
    assert vpad.recebido == [(120, 120)], (
        "reafirmar o mesmo valor não pode nem duplicar o envio nem expirar"
    )


def test_rumble_volta_a_funcionar_depois_de_soltar(ensaio, leitor) -> None:
    """A soltura não é uma porta que tranca: o jogo pode voltar a vibrar."""
    vpad, relogio = ensaio
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    leitor.vivo = False
    _ate_soltar(vpad, relogio)
    assert vpad.recebido[-1] == (0, 0)

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 90, 90))
    assert vpad.recebido[-1] == (90, 90)


def test_silencio_com_motor_ja_parado_e_no_op(ensaio, leitor) -> None:
    """Sem rumble em vigor não há o que soltar, nem consulta, nem um (0,0) supérfluo."""
    vpad, relogio = ensaio
    leitor.vivo = False
    for _ in range(10):
        relogio.avanca(10.0)
        vpad.bombeia()
    assert vpad.recebido == []
    assert leitor.chamadas == 0


def test_fim_de_sessao_limpa_a_conta(ensaio, leitor) -> None:
    """A próxima vida do vpad não herda a conta de consultas mortas da anterior."""
    vpad, _ = ensaio
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    leitor.vivo = False
    vpad.bombeia()
    assert vpad._leitor_mortos == 1
    vpad._silence_rumble()
    assert vpad.recebido[-1] == (0, 0)
    assert vpad._leitor_mortos == 0
    assert vpad._leitor_conferido_em is None
    assert vpad._last_sent == (0, 0)


def test_o_tempo_nao_decide_e_a_consulta_pede_duas_seguidas() -> None:
    """O teto de 3 s saiu (03/11/2026): ele cortava a vibração que o jogo vivo segura.

    Medido em 02/11, sete cortes em uma hora de jogo, todos aos 3,0 s de silêncio, seis
    deles com o motor fraco sustentado `(40, 0)`.
    """
    assert not hasattr(uhid, "_RUMBLE_STALE_SEC"), (
        "o relógio de silêncio voltou, e corta a vibração que o jogo segura de propósito"
    )
    assert uhid._MORTO_POR_SEGUIDAS >= 2, (
        "uma consulta só confunde o jogo que troca de descritor com o jogo morto"
    )
    assert 1.0 <= uhid._CONFERE_O_LEITOR_S <= 10.0


def test_a_parada_do_sdl_e_honrada_em_vez_de_descartada(ensaio) -> None:
    """A causa-raiz do "tremendo sem parar", encontrada em 01/08/2026."""
    vpad, _relogio = ensaio

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 180))
    assert vpad.recebido == [(200, 180)]

    vpad._handle_output(_evento_de_output(0x00, 0, 0, flag1=0x00))

    assert vpad.recebido == [(200, 180), (0, 0)], (
        "a parada do SDL tem de chegar ao motor NA HORA — vem com todos "
        "os flags zerados, e era descartada pelo gate de vibração"
    )


def test_o_report_de_gatilho_continua_sendo_descartado(ensaio) -> None:
    """E o gate continua certo pelo motivo certo — a cura não o afrouxa."""
    vpad, _relogio = ensaio

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 150, 150))
    vpad._handle_output(_evento_de_output(uhid._TRIGGER_FLAGS, 0, 0))

    assert vpad.recebido == [(150, 150)], (
        "o report de gatilho não pode matar a vibração em curso — é o defeito "
        "que o gate de `_VIBRATION_FLAGS` cura, e ele continua de pé"
    )


def test_o_report_de_luz_tambem_continua_sendo_descartado(ensaio) -> None:
    """Idem para lightbar e player-LEDs, que moram no flag1."""
    vpad, _relogio = ensaio

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 90, 90))
    vpad._handle_output(_evento_de_output(0x00, 0, 0, flag1=uhid._LUZ_FLAGS))

    assert vpad.recebido == [(90, 90)]
