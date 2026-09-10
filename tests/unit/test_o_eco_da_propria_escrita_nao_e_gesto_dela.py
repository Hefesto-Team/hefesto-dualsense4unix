"""A borda do botão do microfone não conta o ECO da nossa própria escrita.

O DEFEITO ERA UM LAÇO FECHADO, medido na bancada dela em 10/09/2026 com o
DualSense do rádio na mesa::

    1. o daemon liga o microfone            -> set_microphone_mute(False)
    2. o firmware apaga o bit de mudo
    3. a mudança volta no report de entrada
    4. `_registrar_borda_do_mic` incrementava o contador de bordas
    5. `mic_da_mesa_loop` lia isso como "ela apertou o botão do microfone"
    6. o daemon DESLIGAVA o microfone

No journal dela::

    02:11:15.541  bt_mic_palavra_dela   ligado=True
    02:11:15.547  bt_mic_pedido         ligar=True  seq=4
    02:11:16.164  mic_da_mesa_borda     mudo=True  repiques_engolidos=3  seq=5
    02:11:16.166  bt_mic_pedido         ligar=False seq=5

**620 ms, sem ninguém encostar no controle.** E o áudio captado parava no mesmo
instante: o perfil de energia da gravação dava `53 267 121 102 73 34 35 71` nos
primeiros 800 ms e zero pelo resto — **o microfone captava, e o daemon o
desligava sozinho.**

O contador de bordas está CERTO em existir: o `hid-playstation` consome o botão
do microfone e não o entrega como evento evdev, então a única pista de que ela
apertou é a mudança do bit `STATUS_MIC_MUDO`. O que faltava era distinguir a
mudança que ELA causou da que NÓS causamos.

A MORDIDA: apagar a marca de `set_microphone_mute` (ou o ramo que a consome)
faz `test_o_eco_da_nossa_escrita_nao_conta_borda` reprovar.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO


class _HandleDeMentira:
    """O mínimo do handle real para exercitar o contador de bordas.

    Ele reusa os métodos DE VERDADE do backend — `_registrar_borda_do_mic` e
    `set_microphone_mute` — em vez de reimplementá-los, que é o que faria esta
    régua medir a si mesma.

    **O RELÓGIO É DELE DESDE 10/09/2026**, e sem isso este arquivo não mede
    mais nada: a borda passou a exigir SUSTENTAÇÃO (`SUSTENTACAO_DO_MUDO_S`),
    porque o bit oscila a ~16,7 Hz com o microfone no ar. Um teste que manda a
    mudança e espera a borda no mesmo instante estaria medindo o mundo de
    ontem — e foi exatamente o que aconteceu quando a cura entrou.
    """

    def __init__(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.core import backend_pydualsense as bp
        from hefesto_dualsense4unix.core.backend_pydualsense import (
            _PinnedPyDualSense as _Alvo,
        )

        self._agora = 1000.0
        # O RELÓGIO É DESTE DUBLÊ, e o alvo é ESTREITO — 10/09/2026.
        #
        # A primeira versão fazia `monkeypatch.setattr(bp.time, "monotonic", …)`,
        # e `bp.time` **é o módulo `time` da biblioteca padrão** — o mesmo objeto
        # que o interpretador inteiro usa. A conferência alegou que isso
        # congelava o relógio do PROCESSO e envenenava o vizinho por ordem de
        # teste.
        #
        # **MEDIDO, E O ALCANCE ERA MENOR:** o `monkeypatch` do pytest desfaz ao
        # fim de cada teste, então um vizinho que meça tempo DEPOIS vê o relógio
        # andando. A mordida foi rodada e não pegou.
        #
        # A cura fica assim mesmo, e a razão é outra: trocar um símbolo da
        # stdlib para exercitar UMA guarda nossa é alvo largo demais — alcança
        # todo código que rode dentro do mesmo teste, inclusive o que não está
        # sob prova. `_relogio_da_borda` existe para dar o alvo estreito.
        monkeypatch.setattr(bp, "_relogio_da_borda", lambda: self._agora)
        self._sustentacao = bp.SUSTENTACAO_DO_MUDO_S

        # O ESTADO VEM DO DONO ÚNICO, e não de uma lista redigitada aqui —
        # 10/09/2026. Este bloco listava os cinco campos à mão, e no dia em que
        # a cura da sustentação acrescentou dois, ele ficou mais POBRE que o
        # produto: sete testes deste arquivo morreram no SETUP, com um
        # `AttributeError` que não diz nada sobre sustentação nenhuma.
        self._zerar = _Alvo.zerar_estado_da_borda_do_mic.__get__(self)
        self._garantir_estado_da_borda_do_mic = (
            _Alvo._garantir_estado_da_borda_do_mic.__get__(self)
        )
        self.zerar_estado_da_borda_do_mic = self._zerar
        self._zerar()
        self._mic_mute_desejado: bool | None = None
        self._registrar_borda_do_mic = _Alvo._registrar_borda_do_mic.__get__(self)
        self._marcar_o_mudo_que_pedimos = (
            _Alvo._marcar_o_mudo_que_pedimos.__get__(self)
        )
        self._set_mute = _Alvo.set_microphone_mute.__get__(self)

    def _um_report(self, mudo: bool) -> None:
        self._registrar_borda_do_mic(STATUS_MIC_MUDO if mudo else 0x00)

    def chega_report(self, mudo: bool) -> None:
        """O valor muda E SUSTENTA — é o gesto dela, que trava o bit.

        Dois reports: o que muda (arma) e o que repete depois da janela
        (confirma). É como o fio se comporta quando o dedo dela troca o
        estado: o kernel faz latch e o valor fica.
        """
        self._um_report(mudo)
        self._agora += self._sustentacao + 0.01
        self._um_report(mudo)

    def oscila(
        self, vezes: int, periodo_s: float = 0.06, taxa_hz: float = 170.5
    ) -> None:
        """O GATING do firmware: o bit alterna e NUNCA fica.

        ESTA FUNÇÃO NASCEU FROUXA E FOI APERTADA NA MORDIDA, em 10/09/2026.
        A primeira versão mandava UM report por transição — e com a cura
        arrancada (`SUSTENTACAO_DO_MUDO_S = 0`) os testes continuavam passando,
        porque um valor que nunca se repete nunca sustenta, com janela ou sem.
        **Ela média um cenário que não existe no fio.**

        No fio os reports de entrada chegam a ~170 Hz (medido, em
        `integrations/dualsense_bt_audio`) e o bit oscila a ~16,7 Hz: cada
        valor se REPETE umas dez vezes antes de mudar. É essa repetição que
        faz a sustentação ser uma guarda de verdade — e é ela que tem de estar
        aqui, senão a régua não mede a cura.

        `periodo_s` é a permanência média derivada dos ~16,7 Hz.
        """
        passo = 1.0 / taxa_hz
        valor = bool(self._mic_mudo)
        for _ in range(vezes):
            valor = not valor
            fim = self._agora + periodo_s
            while self._agora < fim:
                self._um_report(valor)   # o MESMO valor, ~10x, como no fio
                self._agora += passo


@pytest.fixture()
def handle(monkeypatch) -> _HandleDeMentira:
    h = _HandleDeMentira(monkeypatch)
    h.chega_report(True)   # a primeira leitura só adota o estado
    assert h._mic_mudo_seq == 0
    return h


def test_o_gating_do_firmware_nao_e_o_dedo_dela(handle: _HandleDeMentira) -> None:
    """40 oscilações a ~16,7 Hz não são 40 apertos — não são aperto nenhum.

    É o defeito de 10/09/2026 que fazia o microfone parar em 1,1 s: o bit
    oscila com o mic no ar, o daemon lia a primeira transição depois do
    debounce como o dedo dela, e desligava o microfone.

    A MORDIDA: ponha `SUSTENTACAO_DO_MUDO_S` em `0` e este teste reprova com
    dezenas de bordas.
    """
    handle.oscila(40)
    assert handle._mic_mudo_seq == 0, (
        f"o gating do firmware virou {handle._mic_mudo_seq} aperto(s) dela — "
        "é o corte de 1,1 s do microfone por rádio"
    )


def test_depois_do_gating_o_dedo_dela_continua_valendo(
    handle: _HandleDeMentira,
) -> None:
    """A cura não pode virar mordaça: o botão tem de sobreviver ao gating."""
    handle.oscila(40)
    estado = bool(handle._mic_mudo)
    handle.chega_report(not estado)
    assert handle._mic_mudo_seq == 1, (
        "depois do gating o aperto dela parou de contar — a guarda virou "
        "mordaça, que é a cura errada"
    )


def test_o_gesto_DELA_conta_borda(handle: _HandleDeMentira) -> None:  # noqa: N802
    """O positivo, e ele vem primeiro: sem isto a cura poderia matar tudo."""
    handle.chega_report(False)
    assert handle._mic_mudo_seq == 1, (
        "o aperto dela no botão do microfone TEM de contar — é a única pista "
        "que existe, porque o hid-playstation consome o botão e não o entrega"
    )


def test_o_eco_da_nossa_escrita_nao_conta_borda(handle: _HandleDeMentira) -> None:
    """O caso EXATO da bancada dela: nós pedimos, e o eco volta."""
    handle._set_mute(False)          # o daemon liga o microfone
    handle.chega_report(False)       # o firmware ecoa a nossa própria ordem
    assert handle._mic_mudo_seq == 0, (
        "o eco da nossa escrita virou «ela apertou o botão» — é o laço de "
        "10/09/2026, que desligava o microfone 620 ms depois de ligá-lo"
    )


def test_o_eco_e_consumido_UMA_vez(handle: _HandleDeMentira) -> None:  # noqa: N802
    """Depois do eco, o botão volta a ser dela — senão a cura vira mordaça."""
    handle._set_mute(False)
    handle.chega_report(False)       # o eco, engolido
    handle.chega_report(True)        # ela apertou de verdade
    assert handle._mic_mudo_seq == 1
    handle.chega_report(False)       # e de novo
    assert handle._mic_mudo_seq == 2


def test_o_gesto_dela_no_sentido_CONTRARIO_ao_que_pedimos_conta(handle) -> None:  # noqa: N802
    """Pedimos «cala» e ela apertou para FALAR: isso é gesto, não eco.

    O estado da fixture é mudo=True. Pedimos `True` — o que já vale, e portanto
    não gera eco nenhum — e então ela aperta e DESMUTA. A mudança existe e vai
    no sentido oposto ao do nosso pedido: é dela, e conta.
    """
    handle._set_mute(True)
    handle.chega_report(False)
    assert handle._mic_mudo_seq == 1, (
        "a marca só cobre a mudança que CASA com o que pedimos; o contrário "
        "é sempre dela"
    )


def test_devolver_a_posse_nao_prevê_eco(handle: _HandleDeMentira) -> None:
    """`None` devolve o campo ao kernel — e não engole borda nenhuma."""
    handle._set_mute(None)
    handle.chega_report(False)
    assert handle._mic_mudo_seq == 1
