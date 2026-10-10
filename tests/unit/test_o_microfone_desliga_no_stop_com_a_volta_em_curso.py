"""O stop do microfone desliga tudo, mesmo quando cai no meio de uma volta.

Sprint O-MICROFONE-DO-RADIO-DESLIGA-NO-STOP-MESMO-COM-A-VOLTA-EM-CURSO-01. A
promessa é do dono (`PonteMicBluetooth`): deixar o microfone de alguém ligado
depois de fechar o programa não é opção. Quem cria (a volta do supervisor) e
quem derruba (o stop) partilham uma porta, e as três réguas abaixo prendem a
volta num `Event` para o stop cair exatamente no meio dela. Nada de aparelho,
servidor de som ou sysfs: a ponte e o canal são dublês que contam o que
ligaram e o que desligaram.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as eleicao
from hefesto_dualsense4unix.integrations import fontes_de_captura as fc

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
ALSA = "alsa_input.usb-Sony_DualSense-00.iec958-stereo"
ESPERA = 5.0


class _PonteDeMentira:
    """Conta o 0x32 de ligar (`iniciar`) e o de desligar (`parar`)."""

    def __init__(self, no: bt.NoDualSenseBT, *, segurar: threading.Event | None = None,
                 entrou: threading.Event | None = None) -> None:
        self.no = no
        self.ligada = False
        self.paradas = 0
        self._segurar = segurar
        self._entrou = entrou

    def iniciar(self) -> bool:
        if self._entrou is not None:
            self._entrou.set()
        if self._segurar is not None:
            assert self._segurar.wait(ESPERA), "a régua não soltou o iniciar"
        self.ligada = True
        return True

    def parar(self) -> None:
        self.ligada = False
        self.paradas += 1


def _no(uniq: str, indice: int) -> bt.NoDualSenseBT:
    return bt.NoDualSenseBT(caminho=f"/dev/hidraw-de-mentira{indice}", uniq=uniq, produto=0x0CE6)


@pytest.fixture
def sem_sistema(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tira da volta tudo o que perguntaria ao sysfs, ao pactl ou ao servidor."""
    monkeypatch.setattr(bt, "_SYSFS_HIDRAW", str(tmp_path / "hidraw"))
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
    for nome in (
        "_aplicar_a_palavra_dela",
        "_renomear_os_canais_velhos",
        "_devolver_a_fonte_padrao",
    ):
        monkeypatch.setattr(bt_mic.BtMicSubsystem, nome, lambda self, *a, **k: None)
    monkeypatch.setattr(bt_mic, "ESPERA_DA_VOLTA_S", 0.05)


def _subsystem(gerenciador: bt.GerenciadorMicBluetooth) -> bt_mic.BtMicSubsystem:
    return bt_mic.BtMicSubsystem(
        gerenciador=gerenciador, registro=bt_mic.RegistroDePedidosDeCanal()
    )


def _espiar_o_parar(gerenciador: bt.GerenciadorMicBluetooth) -> threading.Event:
    """Um sinal que acende quando o stop chega ao `parar()` do gerenciador."""
    parou = threading.Event()
    original = gerenciador.parar

    def _parar() -> None:
        original()
        parou.set()

    gerenciador.parar = _parar  # type: ignore[method-assign]
    return parou


def test_a_ponte_que_a_volta_ergueria_depois_do_stop_nao_sobe(
    sem_sistema: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reprodução de 09/10: o stop passa enquanto a volta está no cabo.

    A volta segue para `gerenciador.reconciliar` depois do `parar()` do
    gerenciador, e sem a porta ela sobe a ponte do P1 (o 0x32 de LIGAR) que
    ninguém mais derruba. MORDIDA: tirar o teste da porta em `reconciliar`.
    """
    criadas: list[_PonteDeMentira] = []

    def _fabrica(no: bt.NoDualSenseBT) -> _PonteDeMentira:
        ponte = _PonteDeMentira(no)
        criadas.append(ponte)
        return ponte

    gerenciador = bt.GerenciadorMicBluetooth(fabrica=_fabrica)
    parou = _espiar_o_parar(gerenciador)
    no_cabo, solta = threading.Event(), threading.Event()

    def _cabo_preso(self: Any, nos: list[Any]) -> None:
        no_cabo.set()
        solta.wait(ESPERA)

    monkeypatch.setattr(bt_mic.BtMicSubsystem, "_reconciliar_o_cabo", _cabo_preso)
    monkeypatch.setattr(bt, "nos_dualsense_bluetooth", lambda: [_no(P1, 1)])
    sub = _subsystem(gerenciador)

    async def _cena() -> threading.Thread | None:
        await sub.start(SimpleNamespace(config=None, controller=None))
        thread = sub._thread
        assert await asyncio.to_thread(no_cabo.wait, ESPERA)
        parando = asyncio.create_task(sub.stop())
        assert await asyncio.to_thread(parou.wait, ESPERA)
        solta.set()
        await parando
        return thread

    thread = asyncio.run(_cena())
    assert thread is not None
    thread.join(ESPERA)
    assert not thread.is_alive()
    assert gerenciador.pontes == {}, f"pontes depois do stop: {gerenciador.pontes!r}"
    ligadas = [p.no.uniq for p in criadas if p.ligada]
    assert ligadas == [], f"microfone ligado depois do stop: {ligadas!r}"
    assert criadas == [], (
        "a volta mandou o 0x32 de LIGAR depois do stop, mesmo que desligue em "
        f"seguida: {[p.no.uniq for p in criadas]!r}"
    )


def test_a_ponte_cujo_iniciar_termina_depois_do_parar_desce(sem_sistema: None) -> None:
    """O `iniciar` ainda corre quando o `parar()` do gerenciador passa.

    A ponte só entraria no dicionário depois, e o `parar()` já o tinha
    esvaziado: ela ficava ligada e fora do alcance de qualquer stop. MORDIDA:
    tirar a descida da ponte tardia.
    """
    entrou, segurar = threading.Event(), threading.Event()
    criadas: list[_PonteDeMentira] = []

    def _fabrica(no: bt.NoDualSenseBT) -> _PonteDeMentira:
        ponte = _PonteDeMentira(no, segurar=segurar, entrou=entrou)
        criadas.append(ponte)
        return ponte

    gerenciador = bt.GerenciadorMicBluetooth(fabrica=_fabrica)
    volta = threading.Thread(target=gerenciador.reconciliar, args=([_no(P1, 1)],))
    volta.start()
    assert entrou.wait(ESPERA)
    gerenciador.parar()
    segurar.set()
    volta.join(ESPERA)
    assert not volta.is_alive()

    assert len(criadas) == 1
    assert criadas[0].ligada is False, "a ponte tardia ficou com o microfone ligado"
    assert criadas[0].paradas == 1
    assert gerenciador.pontes == {}


def test_o_with_do_cli_tem_a_mesma_garantia(sem_sistema: None) -> None:
    """O `with` do CLI sai pelo `parar()`: a volta tardia não religa nada."""
    criadas: list[_PonteDeMentira] = []

    def _fabrica(no: bt.NoDualSenseBT) -> _PonteDeMentira:
        ponte = _PonteDeMentira(no)
        criadas.append(ponte)
        return ponte

    with bt.GerenciadorMicBluetooth(fabrica=_fabrica) as gerenciador:
        gerenciador.reconciliar([_no(P1, 1)])
        assert [p.ligada for p in criadas] == [True]
    gerenciador.reconciliar([_no(P1, 1), _no(P2, 2)])
    assert [p.ligada for p in criadas] == [False]
    assert gerenciador.pontes == {}


def test_p1_no_radio_e_p2_no_cabo_desligam_os_dois(
    sem_sistema: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dois controles ao mesmo tempo, e a volta passa do prazo do stop.

    O canal do P2 (cabo) ainda está nascendo quando o stop desiste de esperar
    a volta e fecha a lista daquele instante; a volta segue e ergue a ponte do
    P1 (rádio). Os dois têm de acabar fora do ar. MORDIDA: tirar o teste de
    `_parar` em `_abrir_os_canais_do_cabo` deixa o canal do P2 de pé.
    """
    criadas: list[_PonteDeMentira] = []

    def _fabrica(no: bt.NoDualSenseBT) -> _PonteDeMentira:
        ponte = _PonteDeMentira(no)
        criadas.append(ponte)
        return ponte

    gerenciador = bt.GerenciadorMicBluetooth(fabrica=_fabrica)
    abrindo, solta = threading.Event(), threading.Event()
    de_pe: dict[str, str] = {}

    class _Canal:
        def __init__(self, uniq: str) -> None:
            self.nome = canal.nome_do_canal(uniq)

    def _abrir(uniq: str, descricao: str, **kw: object) -> _Canal:
        abrindo.set()
        solta.wait(ESPERA)
        de_pe[uniq] = canal.nome_do_canal(uniq)
        return _Canal(uniq)

    def _fechar(uniq: str) -> bool:
        return de_pe.pop(uniq, None) is not None

    monkeypatch.setattr(canal, "abrir", _abrir)
    monkeypatch.setattr(canal, "fechar", _fechar)
    monkeypatch.setattr(canal, "de_pe", lambda: dict(de_pe))
    monkeypatch.setattr(bt, "pactl_mudo", lambda: False)
    monkeypatch.setattr(eleicao, "fontes_de_captura_agora", lambda: [ALSA])
    monkeypatch.setattr(eleicao, "casamento_usb_agora", lambda _m: None)
    monkeypatch.setattr(fc, "escolher_fonte", lambda *a, **k: ALSA)
    monkeypatch.setattr(bt, "nos_dualsense_bluetooth", lambda: [_no(P1, 1)])
    na_mesa = frozenset({fc.so_hex(P1), fc.so_hex(P2)})
    monkeypatch.setattr(bt_mic.BtMicSubsystem, "uniqs_na_mesa", lambda self: na_mesa)
    sub = _subsystem(gerenciador)

    async def _cena() -> threading.Thread | None:
        await sub.start(SimpleNamespace(config=None, controller=None))
        thread = sub._thread
        assert await asyncio.to_thread(abrindo.wait, ESPERA)
        await sub.stop()
        return thread

    thread = asyncio.run(_cena())
    assert thread is not None
    solta.set()
    thread.join(ESPERA)
    assert not thread.is_alive()

    assert de_pe == {}, f"canal do cabo de pé depois do stop: {sorted(de_pe)!r}"
    assert sub._canais_do_cabo == {}
    assert gerenciador.pontes == {}
    ligadas = [p.no.uniq for p in criadas if p.ligada]
    assert ligadas == [], f"microfone do rádio ligado depois do stop: {ligadas!r}"
