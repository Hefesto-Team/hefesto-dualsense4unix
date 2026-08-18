"""A vibração medida nos TRÊS modos — e os instrumentos que mentiam em dois.

Escrito em 09/08/2026, a pedido dela: *"investigar a vibração no modo nativo,
modo xbox e modo dualsense e fazer funcionar em todos"*.

A medição que abriu a investigação, tirada do `state_full` VIVO da máquina
dela, com a máscara DualSense e o jogo aberto::

    plays: 4   nao_nulos: 0   descartados: 0   v2: 0   ff_maior_pedido: [0, 0]

Lida ao pé da letra, ela diz "o jogo pediu vibração 4 vezes e todas com força
zero". Só que **nenhum dos quatro números sabe responder o que perguntam
dele**, e é isso que estes testes travam:

* **máscara Xbox (uinput)** — o backend NUNCA teve `ff_nao_nulo_count` nem
  `ff_maior_pedido`. O `daemon/ipc_handlers` os lê com `getattr(vp, ..., 0)` e
  o painel da aba Rumble pergunta `nao_nulos` ANTES de `plays`: com a máscara
  Xbox funcionando **perfeitamente**, a tela dizia *"o jogo falou de vibração
  Nx, mas pediu força zero em todas"* — e essa frase manda caçar no jogo, que
  é o lado oposto do código. Um modo inteiro do produto era, por construção,
  impossível de medir;

* **máscara DualSense (uhid)** — três buracos deixavam "ninguém pediu nada" e
  "chegou e nós descartamos na porta" saírem com o MESMO painel zerado: o
  report com envelope diferente de 0x02 (descartado antes até do
  `output_count`), a PARADA do SDL (que volta antes do `+= 1`, e é PROVA de
  vibração viva) e a ausência dos bytes crus de quem escreveu;

* **os dois** — `ff_maior_pedido` era guardado com o operador de tupla do
  Python, que compara na ordem lexicográfica: `(1, 0) > (0, 255)` é True, e um
  pedido imperceptível APAGAVA o registro de uma vibração máxima.

Nenhum teste aqui conhece a implementação além do contrato público, e o
relógio é injetado.
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
from hefesto_dualsense4unix.core.rumble import pedido_mais_forte
from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad


class _RelogioFalso:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


# ---------------------------------------------------------------------------
# 1. O maior pedido, comparado por INTENSIDADE (vale para os dois backends)
# ---------------------------------------------------------------------------


def test_o_maior_pedido_e_o_que_a_mao_sente_e_nao_o_primeiro_byte():
    """MORDE: com `>` de tupla no lugar, `(1, 0)` vence `(0, 255)` e passa a ser
    "o maior pedido do jogo" — a tela passa a dizer que o jogo só pediu
    vibração imperceptível quando ele pediu a máxima."""
    assert pedido_mais_forte((0, 255), (1, 0)) == (0, 255)
    assert pedido_mais_forte((0, 0), (0, 255)) == (0, 255)
    assert pedido_mais_forte((10, 10), (200, 3)) == (200, 3)
    # Mesmo pico nos dois: quem sacode mais é quem move os DOIS motores.
    assert pedido_mais_forte((200, 0), (200, 50)) == (200, 50)
    # Empate perfeito de pico E soma mantém o registro antigo (estável).
    assert pedido_mais_forte((0, 255), (255, 0)) == (0, 255)


# ---------------------------------------------------------------------------
# 2. Máscara Xbox (uinput): o modo que era impossível de medir
# ---------------------------------------------------------------------------


class _EfeitoFalso:
    """Um `ff_effect` do kernel, só com o que o parser lê."""

    class _Replay:
        def __init__(self, length: int) -> None:
            self.length = length

    class _Rumble:
        def __init__(self, weak: int, strong: int) -> None:
            self.weak_magnitude = weak
            self.strong_magnitude = strong

    class _U:
        def __init__(self, weak: int, strong: int) -> None:
            self.ff_rumble_effect = _EfeitoFalso._Rumble(weak, strong)

    def __init__(self, ident: int, weak: int, strong: int, duracao_ms: int) -> None:
        from evdev import ecodes

        self.id = ident
        self.type = ecodes.FF_RUMBLE
        self.ff_replay = _EfeitoFalso._Replay(duracao_ms)
        self.u = _EfeitoFalso._U(weak, strong)


@pytest.fixture
def vpad_xbox():
    """Vpad Xbox sem `/dev/uinput`: exercita o catálogo/`_refresh_ff` de verdade.

    Mesma bancada dos testes de FF que já existem — o que precisa ser travado é
    a CONTABILIDADE do caminho real, não uma função isolada.
    """
    from evdev import ecodes

    pad = UinputGamepad.for_flavor("xbox")
    recebido: list[tuple[int, int]] = []
    pad.rumble_sink = lambda w, s: recebido.append((w, s))
    pad.time_fn = _RelogioFalso()
    pad._ff_supported = True
    pad._ecodes = ecodes
    pad.recebido = recebido  # type: ignore[attr-defined]
    return pad


def _carregar_e_tocar(pad, ident: int, weak: int, strong: int, duracao_ms=1000) -> None:
    pad._ff_effects[ident] = pad._parse_ff_effect(
        _EfeitoFalso(ident, weak, strong, duracao_ms)
    )
    pad._start_ff_effect(ident, repeats=1)
    pad._refresh_ff()


def test_mascara_xbox_deixa_de_dizer_forca_zero_com_o_motor_girando(vpad_xbox):
    """MORDE: sem `ff_nao_nulo_count` no backend uinput, o `getattr(..., 0)` do
    `ipc_handlers` devolve 0 e a aba afirma "pediu força zero em todas" com o
    controle sacudindo na mão dela. Arranque a propriedade e este teste cai
    no `assert` do texto."""
    # 0x8000 nos dois motores = metade da escala do kernel -> 128 em 0-255.
    _carregar_e_tocar(vpad_xbox, ident=1, weak=0x8000, strong=0xC000)

    assert vpad_xbox.recebido == [(0x80, 0xC0)], "o par tem de chegar ao sink"
    assert vpad_xbox.ff_play_count == 1
    assert vpad_xbox.ff_nao_nulo_count == 1, "houve FORÇA — e o backend tem de saber"
    assert vpad_xbox.ff_maior_pedido == (0x80, 0xC0)

    # E a frase que ela lê na aba, montada como o daemon a monta.
    estado = {
        "native_mode": False,
        "rumble_ff": {
            "plays": vpad_xbox.ff_play_count,
            "nao_nulos": vpad_xbox.ff_nao_nulo_count,
            "descartados": vpad_xbox.ff_descartado_count,
            "estranhos": 0,
            "vpads": 1,
        },
    }
    assert texto_dos_pedidos_de_vibracao(estado) == (
        "o jogo pediu vibração 1x — se não sentiu, é aqui dentro"
    )


def test_mascara_xbox_guarda_o_maior_por_intensidade(vpad_xbox):
    """MORDE: com a comparação lexicográfica, o pedido fraco de `weak` apaga o
    pedido máximo de `strong` que veio antes."""
    _carregar_e_tocar(vpad_xbox, ident=1, weak=0x0000, strong=0xFF00)
    _carregar_e_tocar(vpad_xbox, ident=1, weak=0x0100, strong=0x0000)

    assert vpad_xbox.ff_maior_pedido == (0, 0xFF), "o pedido MÁXIMO não pode sumir"


def test_mascara_xbox_conta_o_play_de_efeito_que_nao_temos(vpad_xbox):
    """MORDE: sem o contador, um pedido perdido no catálogo é indistinguível de
    "o jogo não pediu" — e o defeito é nosso."""
    vpad_xbox._start_ff_effect(99, repeats=1)

    assert vpad_xbox.ff_play_count == 0, "não tocou nada"
    assert vpad_xbox.ff_descartado_count == 1, "mas o jogo PEDIU"


def test_forca_zero_de_verdade_continua_dizendo_forca_zero(vpad_xbox):
    """A cura não pode virar otimismo: um efeito abaixo de 1/256 da escala NÃO
    move o motor, e contá-lo como força seria a mesma mentira ao contrário."""
    _carregar_e_tocar(vpad_xbox, ident=1, weak=0x00C8, strong=0x0032)

    assert vpad_xbox.ff_play_count == 1
    assert vpad_xbox.ff_nao_nulo_count == 0
    assert vpad_xbox.ff_maior_pedido == (0, 0)


# ---------------------------------------------------------------------------
# 3. Máscara DualSense (uhid): os três buracos do painel
# ---------------------------------------------------------------------------


class _VpadUhidDeBancada(uhid.UhidDualSense):
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
        self._rumble_visto_em = None
        self._rumble_count = 0
        self._output_count = 0
        self._rumble_nao_nulo_count = 0
        self._rumble_maior_pedido = (0, 0)
        self._rumble_descartado_count = 0
        self._rumble_descartado_amostra = None
        self._rumble_v2_count = 0
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
    *,
    report_id: int = uhid._OUTPUT_REPORT_USB,
    flag0: int = 0,
    flag1: int = 0,
    flag2: int = 0,
    weak: int = 0,
    strong: int = 0,
) -> bytes:
    """Monta um UHID_OUTPUT real: 4B de tipo + data[4096] + size + rtype."""
    corpo = bytearray(rep.COMMON_LEN)
    corpo[uhid._VALID_FLAG0_OFFSET] = flag0
    corpo[uhid._VALID_FLAG1_OFFSET] = flag1
    corpo[rep.COMMON_VALID_FLAG2] = flag2
    corpo[uhid._RUMBLE_WEAK_OFFSET] = weak
    corpo[uhid._RUMBLE_STRONG_OFFSET] = strong
    report = bytes([report_id]) + bytes(corpo)
    dados = bytearray(4 + uhid.HID_MAX_DESCRIPTOR_SIZE + 2 + 1)
    dados[4 : 4 + len(report)] = report
    struct.pack_into("<H", dados, 4 + uhid.HID_MAX_DESCRIPTOR_SIZE, len(report))
    return bytes(dados)


_V1 = uhid._VIBRATION_FLAGS
_V2 = rep.VALID_FLAG2_COMPATIBLE_VIBRATION2


@pytest.fixture
def vpad_ds():
    v = _VpadUhidDeBancada(_RelogioFalso())
    try:
        yield v
    finally:
        v.fechar()


def test_report_com_envelope_estranho_deixa_de_sumir_calado(vpad_ds):
    """MORDE: sem o contador, escrita CHEGANDO produz o painel de "nenhum jogo
    enxergou o gamepad virtual" — e as duas conclusões mandam caçar em pontas
    opostas (dedup/udev/máscara x o nosso parser)."""
    vpad_ds._handle_output(_evento_de_output(report_id=0x31, flag0=_V1, weak=200))

    assert vpad_ds.output_count == 0, "não é o 0x02: nada foi lido"
    assert vpad_ds.ff_report_estranho_count == 1, "mas ALGUÉM escreveu"
    assert vpad_ds.ff_report_estranho_amostra == (0x31, rep.COMMON_LEN + 1)

    estado = {
        "native_mode": False,
        "rumble_ff": {"plays": 0, "nao_nulos": 0, "descartados": 0, "estranhos": 1},
    }
    assert "envelope que o Hefesto nem abriu" in (
        texto_dos_pedidos_de_vibracao(estado) or ""
    )


def test_a_parada_do_sdl_deixa_de_ser_invisivel(vpad_ds):
    """MORDE: a parada volta ANTES do `+= 1` do `plays` (certo), e sem contá-la
    "o jogo vibrou e mandou parar" e "ninguém pediu nada" ficam com o MESMO
    painel — quando a parada é prova de vibração viva."""
    vpad_ds._handle_output(_evento_de_output(flag0=_V1, weak=120, strong=90))
    vpad_ds._handle_output(_evento_de_output())  # tudo zerado = parada do SDL

    assert vpad_ds.recebido == [(120, 90), (0, 0)]
    assert vpad_ds.ff_play_count == 1, "a parada NÃO é pedido"
    assert vpad_ds.ff_parada_sdl_count == 1, "mas ela aconteceu, e tem de aparecer"


def test_o_anel_diz_quem_escreveu_e_por_qual_ramo(vpad_ds):
    """MORDE: sem os bytes crus, `plays=4 nao_nulos=0` tem dois autores
    possíveis — o jogo pelo hidraw e o `hid_playstation` traduzindo FF do nó
    evdev — e eles mandam caçar em lugares opostos. O anel os separa."""
    relogio = vpad_ds.time_fn
    vpad_ds._handle_output(_evento_de_output(flag0=_V1, weak=10, strong=20))
    relogio.agora += 2.0
    vpad_ds._handle_output(_evento_de_output(flag2=_V2, weak=30, strong=40))
    relogio.agora += 1.0
    vpad_ds._handle_output(_evento_de_output(flag0=0x0C, weak=77, strong=88))

    anel = vpad_ds.ff_ultimos_reports
    assert [item[-1] for item in anel] == [
        uhid.RAMO_V1,
        uhid.RAMO_V2,
        uhid.RAMO_DESCARTADO,
    ], "cada report tem de dizer por qual ramo entrou"
    assert anel[0][:1] == (3.0,), "a idade sai resolvida em segundos, como o visto_ha_s"
    assert anel[1][1:] == (0, 0, _V2, 30, 40, uhid.RAMO_V2)
    assert anel[2][1:] == (0x0C, 0, 0, 77, 88, uhid.RAMO_DESCARTADO)


def test_o_anel_tem_teto_e_guarda_os_ultimos(vpad_ds):
    """O anel é prova, não histórico: ele vive na thread do poll loop."""
    for i in range(uhid._ANEL_DE_VIBRACAO_MAX + 5):
        vpad_ds._handle_output(_evento_de_output(flag0=_V1, weak=i + 1))

    anel = vpad_ds.ff_ultimos_reports
    assert len(anel) == uhid._ANEL_DE_VIBRACAO_MAX
    assert anel[-1][4] == uhid._ANEL_DE_VIBRACAO_MAX + 5, "o último é o mais novo"


def test_mascara_dualsense_guarda_o_maior_por_intensidade(vpad_ds):
    """MORDE: idem ao uinput — `(1, 0) > (0, 255)` apagaria a vibração máxima."""
    vpad_ds._handle_output(_evento_de_output(flag0=_V1, weak=0, strong=255))
    vpad_ds._handle_output(_evento_de_output(flag0=_V1, weak=1, strong=0))

    assert vpad_ds.ff_maior_pedido == (0, 255)
