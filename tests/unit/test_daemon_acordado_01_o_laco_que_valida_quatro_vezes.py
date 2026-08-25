"""DAEMON-ACORDADO-01 — o laço que validava o MESMO report quatro vezes.

O achado da sprint é um número da máquina dela: **15,2 % de um núcleo com
ninguém jogando**. Este arquivo tranca a fatia que `core/physical_report_reader`
responde por, e a tranca com a régua que sobrevive a máquina de CI.

O DEFEITO
---------
O laço `_read_until_lost` precisa de QUATRO campos do MESMO report — clique do
touchpad, fone/microfone, bateria e a janela de motion — e cada extrator
público começava resolvendo `_struct_base` por conta própria. No rádio o
`_struct_base` valida CRC-32: **quatro CRC-32 por report onde um basta**, mais
as três cópias de buffer que cada `bt_crc32` faz.

POR QUE ESTE PORTÃO CONTA, E NÃO CRONOMETRA
-------------------------------------------
Cronômetro em máquina de CI é a armadilha nº 1 desta casa em outra roupa: o
número muda com a carga da máquina e o teste vira ou frouxo (teto alto demais
para pegar a regressão) ou instável (vermelho por vizinho barulhento). O que
NÃO muda é a **contagem**: um report, uma validação. Duas réguas independentes,
como a casa exige:

* `bt_crc32` — o custo real, e o que a regressão faria voltar a quatro;
* `_struct_base` — a régua que sobrevive a alguém trocar o CRC por algo mais
  barato e continuar resolvendo a base quatro vezes.

O cronômetro está no comentário do módulo, com a data e o hardware. Aqui fica o
que morde.

O DUBLÊ DE LEITOR
-----------------
Um `socketpair(AF_UNIX, SOCK_SEQPACKET)`, não um `os.pipe()`: o pipe é um
STREAM e `os.read(fd, 128)` colaria dois reports de 78 B numa leitura só — o
`SEQPACKET` preserva a fronteira de mensagem como o hidraw preserva a do
report. Fechar a ponta escritora dá EOF, e o laço REAL (`_read_until_lost`,
não uma imitação dele) roda na thread do teste, sem `sleep` e sem corrida.

O relógio é injetado (`time_fn`) para o throttle ser decidido pelo teste, e não
pelo relógio da máquina.
"""
from __future__ import annotations

import contextlib
import os
import socket
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_REPORT_BT_SIZE,
    MOTION_WINDOW_LEN,
    PhysicalReportReader,
)

#: Bit de fone plugado no byte de status do jack (`status[1]`).
_HP_DETECT = 0x01
#: Byte de bateria: nível 9 (95%) descarregando.
_BATERIA = 0x09


def _janela(marca: int) -> bytes:
    """Janela de motion reconhecível e DIFERENTE a cada report.

    Diferente de propósito: o throttle dedupa por VALOR, e uma janela repetida
    não emitiria — o teste passaria a medir o dedup em vez do laço.
    """
    return bytes([(marca + i) & 0xFF for i in range(MOTION_WINDOW_LEN)])


def _usb(marca: int = 1, *, clique: bool = False, jack: int = 0,
         bateria: int = 0) -> bytes:
    raw = bytearray(64)
    raw[0] = prr.INPUT_REPORT_USB
    raw[16 : 16 + MOTION_WINDOW_LEN] = _janela(marca)
    if clique:
        raw[1 + prr.BUTTONS2_OFFSET] |= prr.TOUCHPAD_CLICK_BIT
    raw[1 + prr.JACK_STATUS_OFFSET] = jack
    raw[1 + prr.BATTERY_STATUS_OFFSET] = bateria
    return bytes(raw)


def _bt(marca: int = 1, *, clique: bool = False, jack: int = 0,
        bateria: int = 0, corrompido: bool = False) -> bytes:
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0] = prr.INPUT_REPORT_BT
    raw[1] = 0x01  # contador do BT; o bit de ÁUDIO (0x02) fica DESLIGADO
    raw[17 : 17 + MOTION_WINDOW_LEN] = _janela(marca)
    if clique:
        raw[2 + prr.BUTTONS2_OFFSET] |= prr.TOUCHPAD_CLICK_BIT
    raw[2 + prr.JACK_STATUS_OFFSET] = jack
    raw[2 + prr.BATTERY_STATUS_OFFSET] = bateria
    raw[-4:] = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    if corrompido:
        raw[20] ^= 0xFF  # muda o corpo DEPOIS do CRC
    return bytes(raw)


class _VpadEspiao:
    """Vpad que aceita os quatro caminhos e guarda o que chegou."""

    def __init__(self) -> None:
        self.janelas: list[bytes] = []
        self.cliques: list[bool] = []
        self.jacks: list[int] = []
        self.baterias: list[tuple[int | None, bool]] = []

    def set_motion_streaming(self, ligado: bool) -> None:  # pragma: no cover
        pass

    def forward_motion(self, janela: bytes) -> None:
        self.janelas.append(bytes(janela))

    def forward_touchpad_click(self, apertado: bool) -> None:
        self.cliques.append(apertado)

    def forward_jack(self, status: int) -> None:
        self.jacks.append(status)

    def forward_battery(self, pct: int | None, *, charging: bool,
                        from_reader: bool = False) -> None:
        self.baterias.append((pct, charging))


class _Contador:
    """Conta chamadas de `bt_crc32` e de `_struct_base`, sem mudar o que fazem."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.crc = 0
        self.base = 0
        crc_real, base_real = prr.bt_crc32, prr._struct_base

        def crc_contado(dados: Any, **kw: Any) -> int:
            self.crc += 1
            return crc_real(dados, **kw)

        def base_contada(report: bytes) -> int | None:
            self.base += 1
            return base_real(report)

        monkeypatch.setattr(prr, "bt_crc32", crc_contado)
        monkeypatch.setattr(prr, "_struct_base", base_contada)


def _rodar_o_laco(reports: list[bytes], vpad: Any) -> PhysicalReportReader:
    """Empurra `reports` pelo laço REAL do reader e volta quando der EOF.

    Sem thread e sem `sleep`: o `SEQPACKET` guarda as fronteiras, o `close` da
    ponta escritora vira o `b""` que faz `_read_until_lost` retornar.
    """
    escritor, leitor = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    passo = {"t": 0.0}

    def relogio() -> float:
        passo["t"] += 1.0  # muito além do teto de emissão: nada é engolido
        return passo["t"]

    reader = PhysicalReportReader(
        path_provider=lambda: "/dev/hidraw-dublê", vpad=vpad, time_fn=relogio
    )
    try:
        for r in reports:
            escritor.send(r)
        escritor.close()
        reader._read_until_lost(leitor.fileno())
    finally:
        # O teardown nunca reprova: a ponta escritora já foi fechada acima no
        # caminho feliz, e um erro aqui esconderia o erro de verdade.
        with contextlib.suppress(OSError):
            leitor.close()
        with contextlib.suppress(OSError):
            escritor.close()
    return reader


class TestUmReportUmaValidacao:
    """O portão: a base do report é resolvida UMA vez por report, não quatro."""

    def test_bt_valida_o_crc_uma_vez_por_report(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida principal.

        Com o laço chamando os quatro extratores PÚBLICOS (o estado de antes
        de 25/08/2026), esta contagem sai **4 por report** e o teste reprova.
        """
        contador = _Contador(monkeypatch)
        vpad = _VpadEspiao()
        reports = [_bt(marca=m, jack=_HP_DETECT, bateria=_BATERIA)
                   for m in range(1, 11)]

        reader = _rodar_o_laco(reports, vpad)

        assert reader.reports_seen == 10
        assert contador.crc == 10, (
            f"{contador.crc} validações de CRC-32 para 10 reports de rádio — "
            f"são {contador.crc / 10:.0f} por report. O laço voltou a resolver "
            "a base uma vez por consumidor (DAEMON-ACORDADO-01)."
        )
        assert contador.base == 10, (
            f"{contador.base} resoluções de `_struct_base` para 10 reports. "
            "Esta é a segunda régua: ela pega a regressão mesmo que o CRC "
            "tenha sido trocado por algo mais barato."
        )

    def test_usb_resolve_a_base_uma_vez_por_report(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No cabo não há CRC, mas há as quatro resoluções — e o mesmo teto."""
        contador = _Contador(monkeypatch)
        vpad = _VpadEspiao()
        reports = [_usb(marca=m, jack=_HP_DETECT, bateria=_BATERIA)
                   for m in range(1, 11)]

        reader = _rodar_o_laco(reports, vpad)

        assert reader.reports_seen == 10
        assert contador.crc == 0, "report de cabo não valida CRC nenhum"
        assert contador.base == 10

    def test_report_corrompido_tambem_valida_uma_vez_so(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho do descarte é o que mais tinha a ganhar, e ganhou.

        Antes, um report de rádio corrompido pagava QUATRO CRC-32 para os
        quatro consumidores concluírem, cada um por si, que não sabiam nada
        sobre ele. Agora paga uma — e o `bt_drops` continua contando igual.
        """
        contador = _Contador(monkeypatch)
        vpad = _VpadEspiao()

        reader = _rodar_o_laco([_bt(marca=m, corrompido=True)
                                for m in range(1, 6)], vpad)

        assert reader.reports_seen == 5
        assert reader.bt_drops == 5, "o descarte de CRC ruim tem de continuar contado"
        assert contador.crc == 5
        assert vpad.janelas == [], "rádio corrompido não pode virar motion"


class TestOsQuatroCamposContinuamChegando:
    """A economia não pode ter comido nenhuma das quatro entregas.

    Contar validações sozinho aceitaria a "otimização" que não entrega nada.
    Estes testes são o contrapeso: os mesmos reports, e o que o JOGO veria.
    """

    @pytest.mark.parametrize("fabricar", [_usb, _bt], ids=["cabo", "rádio"])
    def test_clique_jack_bateria_e_motion_saem_do_mesmo_report(
        self, fabricar: Any
    ) -> None:
        vpad = _VpadEspiao()
        reports = [
            fabricar(marca=1),                                  # nada aceso
            fabricar(marca=2, clique=True, jack=_HP_DETECT,
                     bateria=_BATERIA),                         # os três acendem
            fabricar(marca=3, clique=True, jack=_HP_DETECT,
                     bateria=_BATERIA),                         # e seguem acesos
        ]

        reader = _rodar_o_laco(reports, vpad)

        assert reader.reports_seen == 3
        assert vpad.janelas == [_janela(1), _janela(2), _janela(3)]
        assert vpad.cliques == [False, True], "o clique sai por BORDA, não por report"
        assert vpad.jacks == [0, _HP_DETECT]
        # 5 e não 0: a escala do nibble são ONZE níveis (5, 15, ..., 95, 100),
        # então o byte 0x00 é "nível 0 descarregando" = 5%. Ver
        # `decodificar_bateria` — a conta do `dualsense_parse_report` do kernel.
        assert [p for p, _ in vpad.baterias] == [5, 95]
        assert reader.touchpad_clicks == 1
        assert reader.jack_forwards == 2
        assert reader.battery_forwards == 2


class TestAPortaDeQuemSoTemUmReport:
    """Os extratores públicos continuam existindo e continuam corretos.

    Eles são a porta de quem tem UM report na mão (a CLI, um dump, a suíte) e
    não têm base para receber. A equivalência com o caminho quente é o que
    impede as duas metades de divergirem em silêncio — o defeito que a casa
    persegue desde a regra "fato errado sai de TODOS os lugares".
    """

    @pytest.mark.parametrize("fabricar", [_usb, _bt], ids=["cabo", "rádio"])
    def test_com_base_e_sem_base_dao_o_mesmo(self, fabricar: Any) -> None:
        report = fabricar(marca=7, clique=True, jack=_HP_DETECT, bateria=_BATERIA)
        base = prr._struct_base(report)
        assert base is not None

        assert prr._janela_com_base(report, base) == prr.extract_motion_window(report)
        assert prr._clique_com_base(report, base) == prr.extract_touchpad_click(report)
        assert prr._jack_com_base(report, base) == prr.extract_jack_status(report)
        assert prr._bateria_com_base(report, base) == prr.extract_battery_status(report)

    def test_o_extrator_publico_ainda_resolve_a_base_sozinho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quem chama de fora não precisa saber que existe uma base."""
        contador = _Contador(monkeypatch)
        report = _bt(marca=3)

        assert prr.extract_motion_window(report) == _janela(3)

        assert contador.base == 1
        assert contador.crc == 1


class TestOReportDeAudioNaoViraInput:
    """PS-PRESO-01 atravessa a mudança inteira, e é o que mais custou.

    Com o microfone ligado o DualSense manda Opus no MESMO `0x31` de 78 bytes,
    com CRC válido — a única diferença é o bit `0x02` do byte 1. O laço novo
    sai ANTES dos quatro consumidores quando a base é `None`, e é aqui que se
    prova que ele continua saindo: um byte de Opus caindo sobre `buttons[2]`
    foi o que prendeu os botões MIC e PS na máquina dela em 16/08.
    """

    def test_report_de_audio_nao_entrega_nada(self) -> None:
        vpad = _VpadEspiao()
        raw = bytearray(_bt(marca=4, clique=True, jack=_HP_DETECT,
                            bateria=_BATERIA))
        raw[1] |= prr.INPUT_FLAG_AUDIO
        raw[-4:] = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")

        reader = _rodar_o_laco([bytes(raw)], vpad)

        assert reader.reports_seen == 1
        assert vpad.janelas == []
        assert vpad.cliques == [], "Opus não pode virar clique de touchpad"
        assert vpad.jacks == []
        assert vpad.baterias == []
        assert reader.bt_drops == 1


class TestODubleDeLeitorEHonesto:
    """A régua do teste, medida contra si mesma (armadilha nº 1 desta casa).

    Se o `SEQPACKET` colasse dois reports numa leitura — como um `os.pipe()`
    faria —, `reports_seen` viria menor que o número escrito e todas as
    contagens acima estariam medindo outra coisa.
    """

    def test_cada_report_escrito_vira_exatamente_uma_leitura(self) -> None:
        vpad = _VpadEspiao()
        reports = [_bt(marca=m) for m in range(1, 21)]

        reader = _rodar_o_laco(reports, vpad)

        assert reader.reports_seen == 20
        assert len(vpad.janelas) == 20

    def test_o_relogio_e_o_do_teste_e_nao_o_da_maquina(self) -> None:
        """Sem relógio injetado o throttle decidiria, e o teste ficaria frouxo."""
        vpad = _VpadEspiao()
        reader = _rodar_o_laco([_bt(marca=m) for m in range(1, 6)], vpad)
        assert reader.windows_emitted == 5


def test_o_modulo_nao_ficou_com_extrator_orfao() -> None:
    """Os quatro públicos seguem exportados — arrancá-los quebraria a CLI.

    A sprint ENTREGA-QUE-NAO-LIGOU-01 desta casa nasceu do inverso (função sem
    chamador); esta guarda o outro lado: chamador sem função.
    """
    for nome in (
        "extract_motion_window",
        "extract_touchpad_click",
        "extract_jack_status",
        "extract_battery_status",
    ):
        assert callable(getattr(prr, nome)), f"{nome} sumiu do módulo"
    assert os.path.basename(prr.__file__) == "physical_report_reader.py"
