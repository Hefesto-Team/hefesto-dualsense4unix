"""SOM-NAO-MATA-MIC-01 — o som pelo rádio deixou de desligar o microfone.

**A queixa dela, 10/09/2026, com o P1 no rádio:** *"o micr tá ligado e o som
tambme. e tudo saindo ao mesmo tempo."*  <!-- noqa-acento: citação literal dela -->

Medido na bancada dela no mesmo dia, com um gravador ativo na source do
microfone e a ponte do som de pé: **2055 e 2063 reports `0x31` seguidos, todos
com o bit de áudio em ZERO** — nenhum quadro de microfone, com a luz do
microfone acesa e o daemon publicando `mic_mudo: false`.

## A CAUSA, e ela estava escrita no próprio módulo

O `0x35` que leva o som carrega, no primeiro byte do bloco `0x11`, sete bits de
enable — e **o bit 0 é o MICROFONE** (`ENABLES_SEM_MIC = 0xFE`,
`ENABLES_COM_MIC = 0xFF`, medidos em 10/09). O `AltoFalanteSubsystem` construía
`PonteDeSomPorRadio` sem `com_microfone`, logo com o padrão `False` — e a bomba
repetia aquele `0xFE` a **93,75 reports por segundo**.

*O som desligava o microfone noventa e três vezes por segundo.*

É a família de defeito que este lote já pagou duas vezes no mesmo dia (A1 e
A2): **um parâmetro por controle que ninguém injetava**. A diferença é que os
outros dois deixavam uma peça muda; este DESFAZIA o gesto dela.

## E POR QUE O VALOR NÃO PODE SER CONGELADO NA CONSTRUÇÃO

O estado do microfone muda ENQUANTO a ponte está de pé — é ela apertando o
botão. Um `bool` lido uma vez põe todo report seguinte contra o gesto; por isso
`com_microfone` aceita quem RESPONDE, e a bomba pergunta a cada report.

**A MORDIDA de cada teste está na sua docstring.**
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

#: Onde mora o byte dos enables no report montado do `0x35`: o valor do bloco
#: `0x11` começa em [4], e o primeiro byte dele é o dos enables.
POS_ENABLES = 4


def _pcm(quantos: int) -> bytes:
    return bytes(quantos)


def _fonte_infinita() -> Any:
    def _ler(quantos: int) -> bytes:
        return _pcm(quantos)

    return _ler


@pytest.fixture
def arranjo() -> af.Arranjo:
    """O arranjo que TOCOU na bancada dela — o único que conta quadros."""
    return af.ARRANJO_035


def _enables(report: bytes | None) -> int:
    assert report is not None, "a bomba não montou report nenhum"
    return report[POS_ENABLES]


class TestOByteDizOQueOMicrofoneEsta:
    """O contrato do byte, antes de qualquer fiação."""

    def test_sem_mic_e_com_mic_diferem_no_bit_zero(self) -> None:
        """MORDIDA: iguale `ENABLES_COM_MIC` a `ENABLES_SEM_MIC`.

        Os dois valores são medidos de aparelho (10/09/2026). Se um dia
        coincidirem, o produto perdeu a única alavanca que tem sobre o
        microfone dentro do report do som.
        """
        assert af.ENABLES_SEM_MIC == 0xFE
        assert af.ENABLES_COM_MIC == 0xFF
        assert af.ENABLES_COM_MIC ^ af.ENABLES_SEM_MIC == 0b1

    def test_o_bloco_de_controle_carrega_a_escolha(self) -> None:
        """MORDIDA: ignore `com_microfone` em `controle_de_audio_035`."""
        assert af.controle_de_audio_035(
            contador_de_quadros=0, com_microfone=False)[0] == af.ENABLES_SEM_MIC
        assert af.controle_de_audio_035(
            contador_de_quadros=0, com_microfone=True)[0] == af.ENABLES_COM_MIC


class TestABombaPerguntaACadaReport:
    """O coração da cura: a resposta pode mudar no meio da ponte."""

    def test_o_bit_acompanha_o_oraculo_report_a_report(
        self, arranjo: af.Arranjo
    ) -> None:
        """MORDIDA: guarde `bool(com_microfone)` no `__init__` e leia o campo.

        É a forma que o produto tinha até 10/09 — e ela transforma o gesto dela
        num evento que nenhum report seguinte enxerga. Com o congelamento de
        volta, o terceiro report abaixo continua dizendo `0xFE` depois de o
        microfone entrar no ar.
        """
        no_ar = [False]
        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo,
            fonte=_fonte_infinita(),
            com_microfone=lambda: no_ar[0],
        )
        assert _enables(bomba.um_report()) == af.ENABLES_SEM_MIC
        no_ar[0] = True
        assert _enables(bomba.um_report()) == af.ENABLES_COM_MIC
        assert _enables(bomba.um_report()) == af.ENABLES_COM_MIC
        no_ar[0] = False
        assert _enables(bomba.um_report()) == af.ENABLES_SEM_MIC

    def test_o_bool_continua_valendo(self, arranjo: af.Arranjo) -> None:
        """MORDIDA: exija um chamável em `quer_o_microfone`.

        Os ensaios desta casa passam `com_microfone=True` na mão, e quebrar
        isso trocaria um defeito por outro.
        """
        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), com_microfone=True)
        assert _enables(bomba.um_report()) == af.ENABLES_COM_MIC

    def test_um_oraculo_que_explode_nao_cala_o_som(
        self, arranjo: af.Arranjo
    ) -> None:
        """MORDIDA: tire o `try` de `quer_o_microfone`.

        Quem chama está no laço de envio, a 93,75 reports por segundo. Uma
        exceção ali derruba a thread e o som morre por causa de uma pergunta
        sobre o microfone — o remédio matando o paciente.
        """

        def _explode() -> bool:
            raise RuntimeError("o subsystem do mic caiu")

        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), com_microfone=_explode)
        assert _enables(bomba.um_report()) == af.ENABLES_SEM_MIC

    def test_a_ponte_nao_transforma_o_oraculo_em_true(self) -> None:
        """MORDIDA: devolva `self.com_microfone = bool(com_microfone)` à ponte.

        `bool(f)` de uma função é sempre `True`: a ponte ligaria o microfone
        dela para sempre, sem gesto nenhum, e a régua acima continuaria verde
        porque mede a BOMBA. Este teste mede a PONTE.
        """
        ponte = af.PonteDeSomPorRadio(
            uniq="02fe00d4c311",
            abrir_hidraw=lambda: None,
            fonte_de_pcm=_fonte_infinita(),
            com_microfone=lambda: False,
        )
        assert callable(ponte.com_microfone)


class TestAFiacao:
    """O defeito não era a peça: era ninguém a ligar."""

    def test_o_subsystem_do_som_pergunta_ao_do_microfone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: tire `com_microfone=` da fábrica em `alto_falante.py`.

        Sem esse argumento a ponte volta ao padrão `False` — que é o produto
        de antes desta cura, com o `0xFE` no fio 93,75 vezes por segundo.
        """
        from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod

        criadas: list[dict[str, Any]] = []

        class _PonteDeMentira:
            def __init__(self, **kw: Any) -> None:
                criadas.append(kw)
                self.motivo = ""

            def subir(self) -> bool:
                return True

            def descer(self, **_: Any) -> bool:
                return True

        monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
        monkeypatch.setattr(
            af, "fonte_do_monitor_do_no",
            lambda _no, **_k: ((lambda _n: b""), None, ""))

        class _Controle:
            def __init__(self, uniq: str) -> None:
                self.uniq = uniq
                self.caminho = "/dev/hidraw9"
                self.transporte = "bluetooth"

        sub = mod.AltoFalanteSubsystem()
        sub._casar_as_pontes([_Controle("aa:bb:cc:00:00:07")])

        assert criadas, "o subsystem não construiu ponte nenhuma"
        quer = criadas[0].get("com_microfone")
        assert callable(quer), (
            "a ponte nasceu com um valor congelado — o gesto dela no botão do "
            "microfone não alcançaria report nenhum")

        # E o chamável tem de estar amarrado ÀQUELE controle: um oráculo que
        # responde pela mesa inteira poria o microfone do P1 no report do P2.
        vistos: list[str] = []
        anterior = bt.registrar_ouvinte_do_microfone(
            lambda u: bool(vistos.append(u)) or True)
        try:
            assert quer() is True
        finally:
            bt.registrar_ouvinte_do_microfone(anterior)
        assert vistos == ["aa:bb:cc:00:00:07"]

    def test_sem_ouvinte_instalado_a_resposta_e_nao(self) -> None:
        """MORDIDA: faça `o_microfone_esta_no_ar` devolver `True` no escuro.

        Ligar o microfone dela por falta de resposta é o produto tomando por
        ela uma decisão que é do gesto — e sem ninguém na sala para desfazer.
        """
        anterior = bt.registrar_ouvinte_do_microfone(None)
        try:
            assert bt.o_microfone_esta_no_ar("02fe00d4c311") is False
        finally:
            bt.registrar_ouvinte_do_microfone(anterior)


class TestAPortaDoSubsystemDoMicrofone:
    """Quem responde é quem sabe — e ele responde pelo EFEITO."""

    def _sub_com_pontes(self, pontes: dict[str, Any]) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

        class _Ger:
            def __init__(self) -> None:
                self.pontes = pontes

        sub = BtMicSubsystem()
        sub._gerenciador = _Ger()
        return sub

    def _ponte(self, uniq: str, no_ar: bool) -> Any:
        class _No:
            def __init__(self) -> None:
                self.uniq = uniq

        class _Ponte:
            def __init__(self) -> None:
                self.no = _No()
                self.mic_no_ar = no_ar

        return _Ponte()

    def test_responde_pelo_controle_certo(self) -> None:
        """MORDIDA: devolva o estado da PRIMEIRA ponte, sem casar o `uniq`.

        Numa mesa de quatro isso põe o microfone do P1 no report do P4 — o
        mesmo defeito de identidade que `sink_do_controle` já pagou no cabo.
        """
        sub = self._sub_com_pontes({
            "/dev/hidraw1": self._ponte("aa:bb:cc:00:00:01", False),
            "/dev/hidraw2": self._ponte("aa:bb:cc:00:00:02", True),
        })
        assert sub.microfone_no_ar("aa:bb:cc:00:00:02") is True
        assert sub.microfone_no_ar("aa:bb:cc:00:00:01") is False

    def test_o_endereco_normaliza(self) -> None:
        """MORDIDA: compare as duas strings cruas.

        O gesto entrega `aa:bb:cc:00:00:02` e a ponte guarda `aabbcc000002` —
        crus, eles nunca casam, e o microfone nunca entra no report.
        """
        sub = self._sub_com_pontes(
            {"/dev/hidraw2": self._ponte("aabbcc000002", True)})
        assert sub.microfone_no_ar("aa:bb:cc:00:00:02") is True

    def test_sem_gerenciador_a_resposta_e_nao(self) -> None:
        """MORDIDA: deixe `microfone_no_ar` levantar com o subsystem parado."""
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

        assert BtMicSubsystem().microfone_no_ar("aa:bb:cc:00:00:01") is False

    def test_a_ponte_de_mic_confessa_o_pedido(self) -> None:
        """MORDIDA: faça `mic_no_ar` devolver `self._mic_pedido` cru.

        `None` é *"ainda não pedi nada"*, e ele viraria um `None` no bit dos
        enables — que `bool()` resolve para falso por acidente, não por
        decisão. O contrato aqui é de três estados virando dois, e ele é
        explícito.
        """
        ponte = bt.PonteMicBluetooth.__new__(bt.PonteMicBluetooth)
        ponte._mic_pedido = None
        assert ponte.mic_no_ar is False
        ponte._mic_pedido = False
        assert ponte.mic_no_ar is False
        ponte._mic_pedido = True
        assert ponte.mic_no_ar is True
