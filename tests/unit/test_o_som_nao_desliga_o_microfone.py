"""SOM-NAO-MATA-MIC-01 — o som pelo rádio deixou de desligar o microfone."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from tests.unit.o_alto_falante_que_toca import todo_alto_falante_toca

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
        """MORDIDA: iguale `ENABLES_COM_MIC` a `ENABLES_SEM_MIC`."""
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
        """MORDIDA: guarde `bool(com_microfone)` no `__init__` e leia o campo."""
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
        """MORDIDA: exija um chamável em `quer_o_microfone`."""
        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), com_microfone=True)
        assert _enables(bomba.um_report()) == af.ENABLES_COM_MIC

    def test_um_oraculo_que_explode_nao_cala_o_som(
        self, arranjo: af.Arranjo
    ) -> None:
        """MORDIDA: tire o `try` de `quer_o_microfone`."""

        def _explode() -> bool:
            raise RuntimeError("o subsystem do mic caiu")

        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), com_microfone=_explode)
        assert _enables(bomba.um_report()) == af.ENABLES_SEM_MIC

    def test_a_ponte_nao_transforma_o_oraculo_em_true(self) -> None:
        """MORDIDA: devolva `self.com_microfone = bool(com_microfone)` à ponte."""
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
        """MORDIDA: tire `com_microfone=` da fábrica em `alto_falante.py`."""
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
        todo_alto_falante_toca(monkeypatch)

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

        vistos: list[str] = []
        anterior = bt.registrar_ouvinte_do_microfone(
            lambda u: bool(vistos.append(u)) or True)
        try:
            assert quer() is True
        finally:
            bt.registrar_ouvinte_do_microfone(anterior)
        assert vistos == ["aa:bb:cc:00:00:07"]

    def test_sem_ouvinte_instalado_a_resposta_e_nao(self) -> None:
        """MORDIDA: faça `o_microfone_esta_no_ar` devolver `True` no escuro."""
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
        """MORDIDA: devolva o estado da PRIMEIRA ponte, sem casar o `uniq`."""
        sub = self._sub_com_pontes({
            "/dev/hidraw1": self._ponte("aa:bb:cc:00:00:01", False),
            "/dev/hidraw2": self._ponte("aa:bb:cc:00:00:02", True),
        })
        assert sub.microfone_no_ar("aa:bb:cc:00:00:02") is True
        assert sub.microfone_no_ar("aa:bb:cc:00:00:01") is False

    def test_o_endereco_normaliza(self) -> None:
        """MORDIDA: compare as duas strings cruas."""
        sub = self._sub_com_pontes(
            {"/dev/hidraw2": self._ponte("aabbcc000002", True)})
        assert sub.microfone_no_ar("aa:bb:cc:00:00:02") is True

    def test_sem_gerenciador_a_resposta_e_nao(self) -> None:
        """MORDIDA: deixe `microfone_no_ar` levantar com o subsystem parado."""
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

        assert BtMicSubsystem().microfone_no_ar("aa:bb:cc:00:00:01") is False

    def test_a_ponte_de_mic_confessa_o_pedido(self) -> None:
        """MORDIDA: faça `mic_no_ar` devolver `self._mic_pedido` cru."""
        ponte = bt.PonteMicBluetooth.__new__(bt.PonteMicBluetooth)
        ponte._mic_pedido = None
        assert ponte.mic_no_ar is False
        ponte._mic_pedido = False
        assert ponte.mic_no_ar is False
        ponte._mic_pedido = True
        assert ponte.mic_no_ar is True
