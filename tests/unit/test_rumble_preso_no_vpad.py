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
"""
from __future__ import annotations

import contextlib
import os
import struct

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


class _VpadDeBancada(uhid.UhidDualSense):
    """Vpad com o fd desligado — exercita só o caminho de output/rumble.

    Herda o comportamento real de `_handle_output`/`pump_ff`; o que muda é a
    origem dos bytes (o teste os entrega direto) e o relógio.
    """

    def __init__(self, relogio: _RelogioFalso) -> None:
        self.recebido: list[tuple[int, int]] = []
        self.rumble_sink = lambda w, s: self.recebido.append((w, s))
        self.time_fn = relogio
        self.player = 1
        # Um pipe REAL como fd do uhid. Sem isto o `pump_ff` sai na primeira
        # linha (`if fd is None: return`) e o teste passaria mesmo com a cura
        # arrancada — foi o que aconteceu na primeira versão deste arquivo, e é
        # o motivo de a bancada não simplificar o `pump_ff`: o que precisa ser
        # travado é a FIAÇÃO, não a função isolada. A ponta de leitura fica
        # vazia, então o `os.read` levanta BlockingIOError e a drenagem termina
        # como num tique sem evento do jogo.
        self._leitura, self._escrita = os.pipe()
        os.set_blocking(self._leitura, False)
        self._fd = self._leitura
        self._last_sent = (0, 0)
        self._rumble_visto_em = None
        self._rumble_count = 0
        self._output_count = 0
        # QUEM ESCREVEU-01: os campos que o `_handle_output` passou a escrever
        # para dizer QUEM escreveu o report de vibração. Mesma razão do
        # `_visto_em` abaixo: bancada sem `__init__` acompanha campo novo.
        self._rumble_parada_sdl_count = 0
        self._output_id_estranho_count = 0
        self._output_id_estranho_amostra = None
        self._rumble_anel = []
        # PAINEL-DA-VERDADE-01: os carimbos de recência. A bancada lista o
        # estado que usa em vez de chamar o `__init__` do dataclass (ela
        # precisa do fd de pipe), então campo novo entra aqui — e é de
        # propósito que o `_carimbar` NÃO tolere a ausência com um `getattr`:
        # um vpad de produção sem este dicionário é defeito, não um caso a
        # contornar em silêncio.
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


def _evento_de_output(
    flag0: int, weak: int, strong: int, flag1: int = 0
) -> bytes:
    """Monta um UHID_OUTPUT real: 4B de tipo + data[4096] + size + rtype.

    O `flag1` entrou com a cura do furo 6 (BT-E-VPAD-01): o discriminador da
    parada do SDL exige os DOIS flags zerados, e sem poder montar um report
    com flag1 ligado não dá para provar que um report de LUZ continua sendo
    descartado.
    """
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


#: Um report que fala de vibração, e um que não fala.
_COM_VIBRACAO = uhid._VIBRATION_FLAGS
_SO_LIGHTBAR = 0x04


@pytest.fixture
def bancada():
    relogio = _RelogioFalso()
    vpad = _VpadDeBancada(relogio)
    try:
        yield vpad, relogio
    finally:
        vpad.fechar()


def test_stop_normal_do_jogo_continua_chegando(bancada) -> None:
    """O caminho feliz não pode ser sacrificado pela rede de segurança.

    Jogo que para a vibração do jeito certo (report COM os bits e motores em 0)
    tem de ser encaminhado na hora, sem esperar teto de silêncio nenhum.
    """
    vpad, _ = bancada
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 0, 0))
    assert vpad.recebido == [(200, 200), (0, 0)]


def test_report_sem_bits_de_vibracao_nao_mata_a_vibracao_em_curso(bancada) -> None:
    """O gate original: report de lightbar/gatilho NÃO zera o motor.

    É o defeito que `_VIBRATION_FLAGS` cura e que a rede de segurança não pode
    reintroduzir — os bytes 2-3 desses reports vêm zerados e encaminhá-los
    deixava o controle mudo até o jogo mudar o valor de vibração.
    """
    vpad, relogio = bancada
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    for _ in range(50):
        relogio.avanca(0.05)  # ~2,5 s, bem abaixo do teto
        vpad._handle_output(_evento_de_output(_SO_LIGHTBAR, 0, 0))
        vpad.bombeia()
    assert vpad.recebido == [(200, 200)], (
        "report sem bits de vibração não pode encaminhar motor zerado"
    )


def test_rumble_preso_expira_e_o_motor_para(bancada) -> None:
    """O defeito relatado: o stop se perde e o motor gira para sempre.

    Antes desta cura a lista terminava em `[(200, 200)]` e o `report_thread`
    reafirmava esse valor indefinidamente — "tremendo sem parar".
    """
    vpad, relogio = bancada
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    assert vpad.recebido == [(200, 200)]

    # O jogo segue vivo e falando, mas nunca mais menciona vibração.
    relogio.avanca(uhid._RUMBLE_STALE_SEC + 0.1)
    vpad._handle_output(_evento_de_output(_SO_LIGHTBAR, 0, 0))
    vpad.bombeia()

    assert vpad.recebido == [(200, 200), (0, 0)], (
        "passado o teto de silêncio, o motor preso tem de ser zerado"
    )


def test_expiracao_nao_dispara_duas_vezes(bancada) -> None:
    """Zerou uma vez, cala a boca: nada de enxurrada de (0,0) a cada tique."""
    vpad, relogio = bancada
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 180, 180))
    relogio.avanca(uhid._RUMBLE_STALE_SEC + 1.0)
    for _ in range(20):
        relogio.avanca(0.1)
        vpad.bombeia()
    assert vpad.recebido == [(180, 180), (0, 0)]


def test_jogo_que_reafirma_o_mesmo_valor_nao_e_cortado(bancada) -> None:
    """Vibração longa e legítima sobrevive enquanto o jogo a reafirmar.

    O carimbo de "vi vibração" é anterior ao dedup de valor de propósito: quem
    repete o MESMO par está dizendo "ainda quero vibrar", e isso adia o teto
    mesmo não havendo o que reenviar ao hardware.
    """
    vpad, relogio = bancada
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 120, 120))
    for _ in range(10):
        relogio.avanca(uhid._RUMBLE_STALE_SEC * 0.5)
        vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 120, 120))
        vpad.bombeia()
    assert vpad.recebido == [(120, 120)], (
        "reafirmar o mesmo valor não pode nem duplicar o envio nem expirar"
    )


def test_rumble_volta_a_funcionar_depois_de_expirar(bancada) -> None:
    """A expiração não é uma porta que tranca: o jogo pode voltar a vibrar."""
    vpad, relogio = bancada
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    relogio.avanca(uhid._RUMBLE_STALE_SEC + 0.1)
    vpad.bombeia()
    assert vpad.recebido[-1] == (0, 0)

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 90, 90))
    assert vpad.recebido[-1] == (90, 90)


def test_silencio_com_motor_ja_parado_e_no_op(bancada) -> None:
    """Sem rumble em vigor não há o que expirar — nem um (0,0) supérfluo."""
    vpad, relogio = bancada
    relogio.avanca(uhid._RUMBLE_STALE_SEC * 10)
    for _ in range(10):
        vpad.bombeia()
    assert vpad.recebido == []


def test_fim_de_sessao_limpa_o_relogio(bancada) -> None:
    """A próxima vida do vpad não herda o silêncio pendente da anterior."""
    vpad, _ = bancada
    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 200))
    vpad._silence_rumble()
    assert vpad.recebido[-1] == (0, 0)
    assert vpad._rumble_visto_em is None
    assert vpad._last_sent == (0, 0)


def test_teto_veio_de_medicao_e_nao_de_palpite() -> None:
    """A faixa aceitável do teto, e por que ela mudou.

    A primeira versão deste teste exigia ``>= 5.0`` — prudência escrita antes de
    haver qualquer dado. Noventa minutos de jogo real (25/07) produziram 17
    disparos da rede de segurança e desmentiram a premissa: a perda do stop não é
    caso de canto, e sete dos dezessete passavam de 30 em algum motor, ou seja,
    eram SENTIDOS. Com o teto antigo, cada um desses segurava o motor por seis
    segundos — um travamento perceptível a cada treze minutos.

    O piso caiu para o que a evidência sustenta. Um jogo reafirma a vibração
    muitas vezes por segundo enquanto o efeito está vivo (é o que produz a escada
    255 → 127 → 51 → 14 → 3 → 1 medida no log), então um silêncio de segundos no
    meio de uma vibração ativa já é anomalia. O teto continua sendo uma rede de
    segurança, não um cronômetro de efeito.

    O limite de cima segue existindo pelo motivo original: o custo assimétrico.
    Cortar vibração legítima é aborrecimento; motor girando até a bateria acabar
    é desgaste de aparelho.
    """
    assert uhid._RUMBLE_STALE_SEC >= 2.0, (
        "abaixo disto a rede deixa de ser rede e vira cronômetro de efeito — "
        "passaria a cortar vibração sustentada legítima"
    )
    assert uhid._RUMBLE_STALE_SEC <= 6.0, (
        "medido em 25/07: com 6 s, sete travamentos perceptíveis em 90 min de "
        "jogo seguravam o motor pelo teto inteiro"
    )


# ---------------------------------------------------------------------------
# BT-E-VPAD-01, furo 6 — a CURA, e não mais só a mitigação
# ---------------------------------------------------------------------------


def test_a_parada_do_sdl_e_honrada_em_vez_de_descartada(bancada) -> None:
    """A causa-raiz do "tremendo sem parar", encontrada em 01/08/2026.

    O comentário deste módulo dizia, desde 25/07: *"isto é MITIGAÇÃO, não a
    cura. A cura seria descobrir por que o stop se perde"*. Descobriu-se, e
    está no `SDL_hidapi_ps5.c`:

        if (ctx->rumble_left || ctx->rumble_right) {
            effects.ucEnableBits1 |= 0x02;   /* desliga haptics de áudio */
        } else {
            /* deixar os bits desligados restaura os haptics de áudio */
        }

    **Na parada, o SDL emite um report com `valid_flag0 == 0` e os motores
    zerados** — e o gate de `_VIBRATION_FLAGS` descartava exatamente esse
    report. O motor girava até alguém desligar o controle.

    Repare no relógio: a parada chega SEM avanço de tempo nenhum. É isso que
    separa a cura da mitigação — o teto de silêncio precisava de 3 segundos.

    Mordida: apagar o ramo `_e_a_parada_do_sdl` do `_handle_output`.
    """
    vpad, _relogio = bancada

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 200, 180))
    assert vpad.recebido == [(200, 180)]

    # A PARADA do jeito que o SDL a manda: tudo zerado, e na hora.
    vpad._handle_output(_evento_de_output(0x00, 0, 0, flag1=0x00))

    assert vpad.recebido == [(200, 180), (0, 0)], (
        "a parada do SDL tem de chegar ao motor NA HORA — ela vem com todos "
        "os flags zerados, e era descartada pelo gate de vibração"
    )


def test_o_report_de_gatilho_continua_sendo_descartado(bancada) -> None:
    """E o gate continua certo pelo motivo certo — a cura não o afrouxa.

    Um report de gatilho traz os motores zerados por construção. Encaminhá-lo
    mataria a vibração em curso, que é o defeito que o gate cura. O
    discriminador separa os dois casos pelos FLAGS: a parada do SDL tem tudo
    zerado; o report de gatilho tem `flag0 & 0x0C` ligado.

    Mordida: fazer `_e_a_parada_do_sdl` ignorar o `valid_flag0`.
    """
    vpad, _relogio = bancada

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 150, 150))
    vpad._handle_output(_evento_de_output(uhid._TRIGGER_FLAGS, 0, 0))

    assert vpad.recebido == [(150, 150)], (
        "o report de gatilho não pode matar a vibração em curso — é o defeito "
        "que o gate de `_VIBRATION_FLAGS` cura, e ele continua de pé"
    )


def test_o_report_de_luz_tambem_continua_sendo_descartado(bancada) -> None:
    """Idem para lightbar e player-LEDs, que moram no flag1.

    Mordida: tirar o `body[_VALID_FLAG1_OFFSET]` do discriminador. O report de
    luz passa a ser lido como parada e mata a vibração em curso.
    """
    vpad, _relogio = bancada

    vpad._handle_output(_evento_de_output(_COM_VIBRACAO, 90, 90))
    vpad._handle_output(_evento_de_output(0x00, 0, 0, flag1=uhid._LUZ_FLAGS))

    assert vpad.recebido == [(90, 90)]
