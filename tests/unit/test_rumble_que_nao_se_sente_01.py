"""RUMBLE-QUE-NAO-SE-SENTE-01 — a régua que confundia "pediu" com "mencionou".

O relato de 09/08/2026, depois de jogar: *"aparentemente ele voltou a funcionar
com máscaras mas em alguns momentos deixou de funcionar"*. E a medição, tirada
do `state_full` VIVO da máquina dela no mesmo dia, com o jogo já fechado::

    rumble_ff = {"plays": 117, "vpads": 1}
    per_vpad[0] = {"ff_play_count": 117, "output_count": 263, ...}

117 pedidos de vibração e ela sem sentir nada — o que mandaria caçar o defeito
no nosso caminho de saída (sink, política, backend). Só que `ff_play_count` NÃO
conta pedidos de vibração: o `+= 1` do vpad acontece **antes** de os bytes 2-3
serem lidos, então a PARADA (motores em zero) conta igual ao pedido. As 117
podiam ser 117 pedidos de força ZERO, e aí a caça é no jogo — o lado oposto do
código.

Uma régua que não distingue as duas causas não é diagnóstico: é um número que
convence. Estes testes travam a régua nova e o buraco que ela expôs.

O buraco: o gate de vibração olhava só o `valid_flag0`. Existe uma SEGUNDA
codificação — `COMPATIBLE_VIBRATION2`, bit 0x04 do `valid_flag2` —, o firmware
2.21+ a usa, e o nome dela já estava em `core/ds_output_report.py`, usado no
lado de ESCRITA (`core/backend_pydualsense.py`) e nunca no de leitura. Vibração
que chegasse assim era descartada em silêncio, e nada no código sabia dizer que
tinha sido descartada.

Nenhum teste aqui conhece a implementação além do contrato público (o vpad
recebe eventos de output e chama `rumble_sink`), e o relógio é injetado.
"""
from __future__ import annotations

import contextlib
import os
import struct

import pytest

from hefesto_dualsense4unix.app.actions.rumble_actions import (
    texto_dos_pedidos_de_vibracao,
)
from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid


class _RelogioFalso:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


class _VpadDeBancada(uhid.UhidDualSense):
    """Vpad com o fd desligado — exercita só o caminho de output/rumble.

    Mesma bancada do `test_rumble_preso_no_vpad`, pelo mesmo motivo: o que
    precisa ser travado é a FIAÇÃO (`_handle_output` de verdade), não uma
    função isolada.
    """

    def __init__(self, relogio: _RelogioFalso) -> None:
        self.recebido: list[tuple[int, int]] = []
        self.rumble_sink = lambda w, s: self.recebido.append((w, s))
        self.time_fn = relogio
        self.player = 1
        self._leitura, self._escrita = os.pipe()
        os.set_blocking(self._leitura, False)
        self._fd = self._leitura
        self._last_sent = (0, 0)
        self._rumble_visto_em = None
        self._rumble_count = 0
        self._output_count = 0
        self._rumble_nao_nulo_count = 0
        self._rumble_maior_pedido = (0, 0)
        self._rumble_descartado_count = 0
        self._rumble_descartado_amostra = None
        self._rumble_v2_count = 0
        # QUEM ESCREVEU-01: os três campos que o `_handle_output` passou a
        # escrever. A bancada monta o vpad sem `__init__` (o fd é um pipe),
        # então ela é quem tem de acompanhar os campos novos.
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


def _evento_de_output(
    *, flag0: int = 0, flag1: int = 0, flag2: int = 0, weak: int = 0, strong: int = 0
) -> bytes:
    """Monta um UHID_OUTPUT real: 4B de tipo + data[4096] + size + rtype.

    O corpo tem os 47 bytes do `common` inteiros — sem isso o `valid_flag2`
    (offset 38) não caberia, e é justamente ele que estes testes exercitam.
    """
    corpo = bytearray(rep.COMMON_LEN)
    corpo[uhid._VALID_FLAG0_OFFSET] = flag0
    corpo[uhid._VALID_FLAG1_OFFSET] = flag1
    corpo[rep.COMMON_VALID_FLAG2] = flag2
    corpo[uhid._RUMBLE_WEAK_OFFSET] = weak
    corpo[uhid._RUMBLE_STRONG_OFFSET] = strong
    report = bytes([uhid._OUTPUT_REPORT_USB]) + bytes(corpo)
    dados = bytearray(4 + uhid.HID_MAX_DESCRIPTOR_SIZE + 2 + 1)
    dados[4 : 4 + len(report)] = report
    struct.pack_into("<H", dados, 4 + uhid.HID_MAX_DESCRIPTOR_SIZE, len(report))
    return bytes(dados)


_V1 = uhid._VIBRATION_FLAGS
_V2 = rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
#: Um report de GATILHO (flag0 & 0x0C) — o que o gate existe para descartar.
_SO_GATILHO = 0x0C
#: Um report de LUZ (flag1 & 0x04).
_SO_LIGHTBAR = 0x04


@pytest.fixture
def vpad():
    v = _VpadDeBancada(_RelogioFalso())
    try:
        yield v
    finally:
        v.fechar()


# --- a régua: "mencionou" nunca mais é lido como "pediu" ------------------


def test_parada_conta_como_play_mas_nao_como_pedido(vpad):
    """O caso EXATO da mesa dela: `plays` sobe, e o motor nunca mexeria.

    Sem a separação, este cenário devolve `plays=3` — o mesmo número que um
    jogo vibrando de verdade produz — e manda caçar no lado errado.
    """
    for _ in range(3):
        vpad._handle_output(_evento_de_output(flag0=_V1, weak=0, strong=0))

    assert vpad.ff_play_count == 3, "o report FALA de vibração: `plays` conta"
    assert vpad.ff_nao_nulo_count == 0, "força zero: nenhum motor mexeria"
    assert vpad.ff_maior_pedido == (0, 0)


def test_pedido_com_forca_conta_nos_dois_e_guarda_o_maior(vpad):
    vpad._handle_output(_evento_de_output(flag0=_V1, weak=10, strong=20))
    vpad._handle_output(_evento_de_output(flag0=_V1, weak=200, strong=30))
    vpad._handle_output(_evento_de_output(flag0=_V1, weak=5, strong=5))

    assert vpad.ff_play_count == 3
    assert vpad.ff_nao_nulo_count == 3
    assert vpad.ff_maior_pedido == (200, 30), "o maior é o que diz se dava para sentir"


# --- o buraco: a segunda codificação de vibração --------------------------


def test_vibracao_v2_chega_ao_controle(vpad):
    """O bit `COMPATIBLE_VIBRATION2` sozinho é pedido de vibração legítimo.

    ESTE é o teste que morde a cura: com o gate voltando a olhar só o
    `valid_flag0`, `recebido` fica vazio e a vibração some sem deixar rastro —
    que é exatamente o defeito silencioso que se estava caçando.
    """
    vpad._handle_output(_evento_de_output(flag2=_V2, weak=120, strong=90))

    assert vpad.recebido == [(120, 90)], "vibração v2 tem de chegar ao físico"
    assert vpad.ff_nao_nulo_count == 1
    assert vpad.ff_v2_count == 1, "e tem de ficar contada como v2"
    assert vpad.ff_descartado_count == 0


def test_v2_nao_infla_quando_o_jogo_manda_as_duas_codificacoes(vpad):
    """`ff_v2_count` mede o que SÓ o ramo novo salvou — não todo pedido."""
    vpad._handle_output(_evento_de_output(flag0=_V1, flag2=_V2, weak=50, strong=50))

    assert vpad.recebido == [(50, 50)]
    assert vpad.ff_v2_count == 0, "o flag0 já bastava: o ramo v2 não salvou nada"


# --- o silêncio que não pode voltar: descarte contado ---------------------


def test_pedido_em_codificacao_desconhecida_e_contado_com_amostra(vpad):
    """Motor não-nulo sem nenhum bit conhecido: descartar sim, calar não.

    Sem o contador, a tela afirmaria "o jogo não pediu vibração" com o pedido
    na mão — a mentira mais cara que a aba poderia contar.
    """
    vpad._handle_output(_evento_de_output(flag1=0x20, weak=77, strong=88))

    assert vpad.recebido == [], "sem bit conhecido, encaminhar seria chutar"
    assert vpad.ff_descartado_count == 1
    assert vpad.ff_descartado_amostra == (0x00, 0x20, 0x00, 77, 88)


def test_gatilho_e_luz_nao_inflam_o_descarte(vpad):
    """RUMBLE-PRESO-01 continua de pé: report sem vibração traz motor zerado.

    Se o descarte contasse reports de motor zerado, ele subiria a 60 Hz em
    qualquer jogo com gatilhos adaptativos e a tela acusaria defeito nosso o
    tempo todo — um alarme convincente e falso.
    """
    for _ in range(20):
        vpad._handle_output(_evento_de_output(flag0=_SO_GATILHO))
        vpad._handle_output(_evento_de_output(flag1=_SO_LIGHTBAR))

    assert vpad.ff_descartado_count == 0
    assert vpad.ff_play_count == 0
    assert vpad.recebido == []


def test_report_curto_nao_derruba_o_pump(vpad):
    """Report menor que o `common` não pode levantar IndexError no flag2."""
    curto = bytearray(4 + uhid.HID_MAX_DESCRIPTOR_SIZE + 2 + 1)
    report = bytes([uhid._OUTPUT_REPORT_USB, _V1, 0x00, 44, 55])
    curto[4 : 4 + len(report)] = report
    struct.pack_into("<H", curto, 4 + uhid.HID_MAX_DESCRIPTOR_SIZE, len(report))

    vpad._handle_output(bytes(curto))

    assert vpad.recebido == [(44, 55)]


# --- a janela: qual das duas causas ela lê --------------------------------


def _estado(**ff):
    return {"native_mode": False, "rumble_ff": {"vpads": 1, **ff}}


def test_janela_separa_pedido_de_forca_zero():
    """As duas frases têm de ser DIFERENTES — elas mandam caçar em lados opostos."""
    pediu = texto_dos_pedidos_de_vibracao(_estado(plays=117, nao_nulos=9))
    calou = texto_dos_pedidos_de_vibracao(_estado(plays=117, nao_nulos=0))

    assert pediu == "o jogo pediu vibração 9x — se não sentiu, é aqui dentro"
    assert calou == "o jogo falou de vibração 117x, mas pediu força zero em todas"
    assert pediu != calou


def test_janela_denuncia_o_formato_que_nao_reconhecemos():
    txt = texto_dos_pedidos_de_vibracao(_estado(plays=0, nao_nulos=0, descartados=4))

    assert txt is not None
    assert "4x" in txt
    assert "não reconheceu" in txt
    assert "defeito nosso" in txt


def test_janela_com_daemon_velho_nao_inventa_causa():
    """Sem `nao_nulos` no payload, a linha volta ao texto antigo — e só a ele.

    Um daemon mais velho não manda o campo. Afirmar qualquer uma das duas
    causas aí seria repetir, com outro texto, o defeito que esta leva cura.
    """
    txt = texto_dos_pedidos_de_vibracao(_estado(plays=117))

    assert txt == "o jogo pediu vibração 117x"


def test_janela_cala_quando_nao_sabe():
    assert texto_dos_pedidos_de_vibracao({"native_mode": False}) is None


def test_janela_respeita_a_conexao_nativa():
    txt = texto_dos_pedidos_de_vibracao({"native_mode": True, "rumble_ff": {"plays": 0}})

    assert txt == "Conexão Nativa (Sony): o jogo fala direto com o controle"
