"""O número que se solta é o que acende — A-NUMERACAO-BATE-A-LUZ-COM-O-JOGO-01, cura 1."""

from __future__ import annotations

import asyncio
import math
import re
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import structlog

import hefesto_dualsense4unix.daemon.connection as cx
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    ATRASO_APOS_A_ULTIMA_CONEXAO_S,
    COMMON_PLAYER_LEDS,
)
from hefesto_dualsense4unix.core.sysfs_leds import SysfsLedNode
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    make_auto_output_provider,
    prazo_do_lugar_guardado,
)
from tests.unit.test_coop_bancada_de_queda_do_primario import _FakeHandle
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    P1,
    P2,
    P3,
    P4,
    TRANSPORTES,
    UNIQS,
    MesaDoJogo,
    Relogio,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    config_isolado as config_isolado,
)
from tests.unit.test_o_numero_do_jogador_se_reorganiza_na_hora import _Tempo

QUATRO = (P1, P2, P3, P4)
PRAZO = prazo_do_lugar_guardado()
TIQUE = 2.0

PLAYER_IDS = {1: 0x04, 2: 0x0A, 3: 0x15, 4: 0x1B}
NUMERO_DO_VALOR = {valor: numero for numero, valor in PLAYER_IDS.items()}
_FLAG1_DO_NUMERO = 0x10
_COMMON_NO_RADIO = 3


def _numero_dos_bits(bits: tuple[bool, ...]) -> int | None:
    valor = sum(1 << i for i, aceso in enumerate(bits) if aceso)
    return NUMERO_DO_VALOR.get(valor)


def _numero_do_report(report: bytes) -> int | None:
    """O número que um ``0x31`` acende, ou None se ele não fala do número."""
    if not report[_COMMON_NO_RADIO + 1] & _FLAG1_DO_NUMERO:
        return None
    return NUMERO_DO_VALOR.get(report[_COMMON_NO_RADIO + COMMON_PLAYER_LEDS])


class _HandleQueGuarda(_FakeHandle):
    """O handle da bancada de queda que guarda cada report escrito, e em que fio."""

    def __init__(self, transporte: str) -> None:
        super().__init__(transporte)
        self.reports: list[tuple[int, bytes]] = []

    def writeReport(self, report: list[int]) -> int:  # noqa: N802 — API pydualsense
        self.reports.append((threading.get_ident(), bytes(report)))
        return len(report)


class _NoQueGuarda(SysfsLedNode):
    """O nó de LED de verdade, num diretório temporário, que anota o ``set_players``."""

    def __init__(self, raiz: Path) -> None:
        raiz.mkdir(parents=True, exist_ok=True)
        indicador = raiz / "rgb:indicator"
        indicador.mkdir(exist_ok=True)
        (indicador / "multi_intensity").write_text("0 0 255\n")
        (indicador / "brightness").write_text("255\n")
        jogadores = []
        for n in range(1, 6):
            pasta = raiz / f"white:player-{n}"
            pasta.mkdir(exist_ok=True)
            (pasta / "brightness").write_text("0\n")
            jogadores.append(str(pasta))
        super().__init__(str(indicador), jogadores)
        self.numeros: list[int | None] = []

    def set_players(self, bits: tuple[bool, bool, bool, bool, bool]) -> bool:
        self.numeros.append(_numero_dos_bits(tuple(bits)))
        return super().set_players(bits)


class MesaDaLuz(MesaDoJogo):
    """A bancada de jogo aberto com o que escreve a luz: handles e nós que guardam."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, tmp: Path, *, jogo: bool
    ) -> None:
        relogio = Relogio()
        super().__init__(monkeypatch, relogio=relogio, tempo=relogio, jogo=jogo)
        self.relogio = relogio
        self.handles: dict[str, _HandleQueGuarda] = {}
        self.nos: dict[str, _NoQueGuarda] = {}
        self._tmp = tmp
        self.inst.set_auto_output_provider(make_auto_output_provider(self.reg))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.sysfs_leds.discover",
            lambda: {u: self._no_de(u) for u in self.mesa.nodes},
        )
        monkeypatch.setattr(cx, "time", _Tempo(relogio))
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="executor")
        self.fio_do_executor: set[int] = set()

        async def _run_blocking(fn: Callable[..., Any], *args: Any) -> Any:
            def _anotar() -> Any:
                self.fio_do_executor.add(threading.get_ident())
                return fn(*args)

            return await asyncio.get_running_loop().run_in_executor(self.executor, _anotar)

        self.daemon._run_blocking = _run_blocking

    def _no_de(self, uniq: str) -> _NoQueGuarda:
        if uniq not in self.nos:
            self.nos[uniq] = _NoQueGuarda(self._tmp / uniq)
        return self.nos[uniq]

    def connect(self) -> None:
        vistos = self.mesa.como_o_backend_ve()
        por_path = {
            path: uniq
            for (_key, path, _edge), uniq in zip(vistos, self.mesa.nodes, strict=True)
        }

        def _abrir(path: bytes, *, is_edge: bool) -> _HandleQueGuarda:
            uniq = por_path[path]
            handle = _HandleQueGuarda(self.mesa.transporte_de(uniq))
            self.handles[uniq] = handle
            return handle

        with patch.object(
            PyDualSenseController, "_enumerate_device_keys", return_value=vistos
        ), patch.object(PyDualSenseController, "_open_one", side_effect=_abrir):
            self.inst.connect()


    def limpar(self) -> None:
        for handle in self.handles.values():
            handle.reports.clear()
        for no in self.nos.values():
            no.numeros.clear()

    def no_radio(self, uniq: str) -> bool:
        return self.mesa.transporte_de(uniq) == "bt"

    def o_que_acendeu(self, uniq: str) -> list[int | None]:
        """Os números escritos neste controle, na ordem: o ``0x31`` no rádio, o nó no cabo."""
        if self.no_radio(uniq):
            return [
                n for _fio, r in self.handles[uniq].reports
                if (n := _numero_do_report(r)) is not None
            ]
        return list(self.nos[uniq].numeros)

    def disparar(self) -> int:
        """O ``disparar_gatilhos_devidos`` de produção num laço ``asyncio``."""
        return asyncio.run(cx.disparar_gatilhos_devidos(self.daemon))

    def fechar(self) -> None:
        self.executor.shutdown(wait=True)


@pytest.fixture
def mesa_da_luz(
    config_isolado: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Callable[..., MesaDaLuz]]:
    criadas: list[MesaDaLuz] = []

    def _montar(transporte: str = "bt", *, jogo: bool = False, quantos: int = 4) -> MesaDaLuz:
        bancada = MesaDaLuz(monkeypatch, tmp_path, jogo=jogo)
        criadas.append(bancada)
        for uniq, via in zip(UNIQS[:quantos], TRANSPORTES[transporte][:quantos], strict=True):
            bancada.mesa.sentar(uniq, transporte=via)
        for _ in range(3):
            bancada.tique()
        assert bancada.reg.liberar_as_lampadas() is True
        bancada.tique()
        esperado = {UNIQS[n]: n + 1 for n in range(quantos)}
        assert bancada.a_tela() == esperado
        assert cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon) is False
        return bancada

    yield _montar
    for bancada in criadas:
        bancada.fechar()


def _a_volta_e_o_disparo(bancada: MesaDaLuz) -> None:
    """A volta do laço confere a numeração, e o gatilho dispara se ela armou."""
    if cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon):
        bancada.relogio.avancar(ATRASO_APOS_A_ULTIMA_CONEXAO_S + 0.1)
        bancada.disparar()


def _sai_e_o_prazo_passa(bancada: MesaDaLuz, sai: str) -> dict[str, int]:
    """``sai`` levanta, o prazo passa nos tiques, e a fatia arma. Devolve a conta."""
    ordem = [u for u in UNIQS if u in bancada.mesa.nodes]
    bancada.mesa.levantar(sai)
    bancada.tique()
    _a_volta_e_o_disparo(bancada)
    assert bancada.reg.numeros_da_mesa() == {
        u: n + 1 for n, u in enumerate(ordem) if u != sai
    }, "dentro do prazo ninguém troca de número (D-2409)"
    for _ in range(math.ceil(PRAZO / TIQUE) + 1):
        bancada.tique()
    if bancada.daemon.display_authority == "game":
        # D-3009-COM-O-JOGO-O-LUGAR-GUARDADO-ESPERA (dela, 02/10/2026): com o jogo
        # na autoridade o prazo para, e a fatia arma quando o jogo solta e o
        # prazo que sobrou passa.
        assert bancada.reg.numeros_da_mesa() == {
            u: n + 1 for n, u in enumerate(ordem) if u != sai
        }, "com o jogo aberto ninguém renumera por quem saiu (D-3009)"
        assert cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon) is False
        bancada.daemon.display_authority = "daemon"
        for _ in range(math.ceil(PRAZO / TIQUE) + 1):
            bancada.tique()
    conta = {u: n + 1 for n, u in enumerate(u for u in ordem if u != sai)}
    andou = conta != {u: n + 1 for n, u in enumerate(ordem) if u != sai}
    assert cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon) is andou, (
        "o prazo venceu e a fatia não armou" if andou
        else "quem saiu era o último: ninguém troca de número, e nada arma"
    )
    bancada.relogio.avancar(ATRASO_APOS_A_ULTIMA_CONEXAO_S + 0.1)
    bancada.limpar()
    return conta if andou else {}


SAI = pytest.mark.parametrize("sai", QUATRO, ids=["sai-p1", "sai-p2", "sai-p3", "sai-p4"])
VIA = pytest.mark.parametrize("transporte", ["bt", "usb", "mista"])
JOGO = pytest.mark.parametrize("jogo", [False, True], ids=["sem-jogo", "com-jogo"])


class TestOPrimeiroReportDizONumeroNovo:
    @JOGO
    @VIA
    @SAI
    def test_o_disparo_acende_a_conta(
        self, mesa_da_luz: Callable[..., MesaDaLuz], sai: str, transporte: str, jogo: bool
    ) -> None:
        bancada = mesa_da_luz(transporte, jogo=jogo)
        esperado = _sai_e_o_prazo_passa(bancada, sai)
        assert bancada.disparar() == (1 if esperado else 0), "o gatilho e a conta discordam"
        for uniq, numero in esperado.items():
            acendeu = bancada.o_que_acendeu(uniq)
            assert acendeu, f"{uniq} não recebeu escrita no disparo"
            assert acendeu[0] == numero, (
                f"{uniq}: o disparo acendeu {acendeu} e a conta diz {numero} "
                f"(saiu {sai}, {transporte}, jogo={jogo}) — o 03:07:55"
            )


class TestUmaEscritaPorControle:
    @VIA
    @SAI
    def test_um_report_no_radio_um_set_players_no_cabo(
        self, mesa_da_luz: Callable[..., MesaDaLuz], sai: str, transporte: str
    ) -> None:
        bancada = mesa_da_luz(transporte)
        esperado = _sai_e_o_prazo_passa(bancada, sai)
        bancada.disparar()
        for uniq in esperado:
            assert len(bancada.o_que_acendeu(uniq)) == 1, (
                f"{uniq} ({bancada.mesa.transporte_de(uniq)}): "
                f"{bancada.o_que_acendeu(uniq)} — duas fatias do rádio por nada"
            )


class TestOFioDeCadaUm:
    def test_o_preparo_no_laco_a_escrita_no_executor(
        self, mesa_da_luz: Callable[..., MesaDaLuz], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bancada = mesa_da_luz("bt")
        _sai_e_o_prazo_passa(bancada, P2)
        publicacoes: list[int] = []
        publicar = bancada.inst.set_coop_outputs

        def espiao(*a: Any, **kw: Any) -> Any:
            publicacoes.append(threading.get_ident())
            return publicar(*a, **kw)

        monkeypatch.setattr(bancada.inst, "set_coop_outputs", espiao)
        fio_do_laco = threading.get_ident()
        bancada.disparar()
        assert publicacoes, "o disparo não republicou a camada do co-op"
        assert set(publicacoes) == {fio_do_laco}, (
            "a camada do co-op foi publicada fora do fio do laço"
        )
        escritas = {fio for h in bancada.handles.values() for fio, _r in h.reports}
        assert escritas and escritas <= bancada.fio_do_executor, (
            "a escrita do gatilho saiu do executor"
        )


class TestORenumerarEAVoltaTardia:
    @VIA
    def test_o_renumerar_agora(
        self, mesa_da_luz: Callable[..., MesaDaLuz], transporte: str
    ) -> None:
        bancada = mesa_da_luz(transporte)
        bancada.mesa.levantar(P2)
        bancada.tique()
        _a_volta_e_o_disparo(bancada)
        bancada.reg.soltar_os_lugares_guardados(motivo="renumerar")
        assert cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon) is True
        bancada.relogio.avancar(ATRASO_APOS_A_ULTIMA_CONEXAO_S + 0.1)
        bancada.limpar()
        bancada.disparar()
        for uniq, numero in {P1: 1, P3: 2, P4: 3}.items():
            assert bancada.o_que_acendeu(uniq)[:1] == [numero], (
                f"{uniq}: {bancada.o_que_acendeu(uniq)}, a conta diz {numero}"
            )

    def test_o_p1_que_volta_depois_do_prazo(
        self, mesa_da_luz: Callable[..., MesaDaLuz]
    ) -> None:
        """O lugar do P1 se solta pelo «Renumerar agora», e ele volta com o jogo aberto.

        D-3009-COM-O-JOGO-O-LUGAR-GUARDADO-ESPERA (dela, 02/10/2026): com o jogo
        na autoridade o prazo não vence; o que solta o lugar de quem saiu, no
        meio da partida, é o gesto dela.
        """
        bancada = mesa_da_luz("mista", jogo=True)
        via = bancada.mesa.transporte_de(P1)
        bancada.mesa.levantar(P1)
        for _ in range(math.ceil(PRAZO / TIQUE) + 1):
            bancada.tique()
        assert bancada.reg.numeros_da_mesa() == {P2: 2, P3: 3, P4: 4}, (
            "com o jogo aberto o prazo do P1 venceu (D-3009)"
        )
        bancada.reg.soltar_os_lugares_guardados(motivo="renumerar")
        assert cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon) is True
        bancada.relogio.avancar(ATRASO_APOS_A_ULTIMA_CONEXAO_S + 0.1)
        bancada.disparar()
        bancada.mesa.sentar(P1, transporte=via)
        for _ in range(3):
            bancada.tique()
        assert cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon) is True
        bancada.relogio.avancar(ATRASO_APOS_A_ULTIMA_CONEXAO_S + 0.1)
        bancada.limpar()
        bancada.disparar()
        conta = {P1: 1, P2: 2, P3: 3, P4: 4}
        assert bancada.a_tela() == conta, f"a conta e a tela discordam: {bancada.a_tela()}"
        for uniq, numero in conta.items():
            assert bancada.o_que_acendeu(uniq)[:1] == [numero], (
                f"{uniq}: {bancada.o_que_acendeu(uniq)}, a conta diz {numero}"
            )


_MASCARADO = re.compile(r"^[0-9a-f]{6}0000[0-9a-f]{2}$")


class TestODiarioDizONumero:
    def test_o_gatilho_diz_o_numero_que_escreveu(
        self, mesa_da_luz: Callable[..., MesaDaLuz]
    ) -> None:
        bancada = mesa_da_luz("bt")
        esperado = _sai_e_o_prazo_passa(bancada, P2)
        with structlog.testing.capture_logs() as registros:
            bancada.disparar()
        escritos = [r for r in registros if r["event"] == "gatilho_da_cor_escrito"]
        assert sorted(r["numero"] for r in escritos) == sorted(esperado.values()), escritos

    def test_a_camada_do_coop_escrita_uma_vez_por_mudanca(self) -> None:
        """A camada que o co-op publica COM escrita diz o número, mascarado, em ``info``."""
        from hefesto_dualsense4unix.core.controller import OutputSpec
        from hefesto_dualsense4unix.core.led_control import player_led_pattern
        from tests.unit.test_backend_multi_controller import _null_evdev

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        chave = "AA:BB:CC:12:34:02"
        inst._handles = {chave: _HandleQueGuarda("bt")}  # type: ignore[assignment]
        camada = {"aabbcc123402": OutputSpec(player_leds=player_led_pattern(2))}
        with structlog.testing.capture_logs() as registros:
            inst.set_coop_outputs(camada)
            inst.set_coop_outputs(camada)
        linhas = [r for r in registros if r["event"] == "camada_do_coop_escrita"]
        assert len(linhas) == 1, linhas
        assert linhas[0]["log_level"] == "info"
        numeros = linhas[0]["numeros"]
        assert list(numeros.values()) == [2]
        assert all(_MASCARADO.match(endereco) for endereco in numeros), numeros


class TestSemCoOp:
    def test_um_controle_so_acende_pela_automatica(
        self, mesa_da_luz: Callable[..., MesaDaLuz], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bancada = mesa_da_luz("bt", quantos=1)
        publicacoes: list[Any] = []
        publicar = bancada.inst.set_coop_outputs
        monkeypatch.setattr(
            bancada.inst,
            "set_coop_outputs",
            lambda *a, **kw: publicacoes.append((a, kw)) or publicar(*a, **kw),
        )
        bancada.reg.soltar_os_lugares_guardados(motivo="renumerar")
        cx.armar_gatilho_da_cor_por_evento(bancada.daemon, "teste")
        bancada.relogio.avancar(ATRASO_APOS_A_ULTIMA_CONEXAO_S + 0.1)
        bancada.limpar()
        bancada.disparar()
        assert publicacoes == [], f"o preparo publicou camada sem secundário: {publicacoes}"
        assert bancada.inst._desired_coop_by_uniq == {}
        assert bancada.o_que_acendeu(P1) == [1]


class TestQuemChegaSemLiberacao:
    def test_a_estreia_acende_sem_esperar_o_gatilho(
        self, mesa_da_luz: Callable[..., MesaDaLuz]
    ) -> None:
        bancada = mesa_da_luz("bt", quantos=3)
        bancada.limpar()
        bancada.mesa.sentar(P4, transporte="bt")
        bancada.tique()
        assert bancada.o_que_acendeu(P4)[-1:] == [4], (
            f"o quarto estreou sem acender o 4: {bancada.o_que_acendeu(P4)}"
        )

    def test_a_camada_publicada_entre_duas_liberacoes_nao_chega_ao_disparo(
        self, mesa_da_luz: Callable[..., MesaDaLuz]
    ) -> None:
        """As 16 trocas do diário: uma publicação qualquer no meio, e o disparo seguinte."""
        bancada = mesa_da_luz("bt")
        bancada.mesa.levantar(P2)
        bancada.tique()
        _a_volta_e_o_disparo(bancada)
        for _ in range(math.ceil(PRAZO / TIQUE) + 1):
            bancada.tique()
        bancada.coop.sync(force=True)
        assert cx.armar_gatilho_da_cor_por_numeracao(bancada.daemon) is True
        bancada.relogio.avancar(ATRASO_APOS_A_ULTIMA_CONEXAO_S + 0.1)
        bancada.limpar()
        bancada.disparar()
        for uniq, numero in {P1: 1, P3: 2, P4: 3}.items():
            assert bancada.o_que_acendeu(uniq)[:1] == [numero], (
                f"{uniq}: {bancada.o_que_acendeu(uniq)}, a conta diz {numero}"
            )


class _Luz:
    """O ``handle.light`` da pydualsense: o número que o ``report_thread`` leva pelo cabo."""

    def __init__(self) -> None:
        self.playerNumber: int | None = None

    def setColorI(self, *_rgb: int) -> None:  # noqa: N802 — API pydualsense
        pass


class TestOCaboSemONo:
    @pytest.mark.parametrize("sai", (P1, P2, P3), ids=["sai-p1", "sai-p2", "sai-p3"])
    def test_o_cabo_sem_o_no_de_led_acende_a_conta(
        self, mesa_da_luz: Callable[..., MesaDaLuz], monkeypatch: pytest.MonkeyPatch, sai: str
    ) -> None:
        """O cabo sem nó de LED gravável (sem a regra 77), o caminho degradado de sempre."""
        bancada = mesa_da_luz("usb")
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.sysfs_leds.discover",
            lambda: {u: bancada._no_de(u) for u in bancada.mesa.nodes if u != P4},
        )
        luz = _Luz()
        bancada.handles[P4].light = luz  # type: ignore[attr-defined]
        bancada.tique()
        assert P4 not in {
            bancada.inst._key_to_uniq(k) for k in bancada.inst._sysfs
        }, "a bancada não tirou o nó do P4"
        esperado = _sai_e_o_prazo_passa(bancada, sai)
        assert esperado[P4] == 3, esperado
        bancada.disparar()
        for _ in range(3):
            bancada.tique()
        assert luz.playerNumber is not None and int(luz.playerNumber) == PLAYER_IDS[3], (
            f"o P4 (cabo sem nó) acende {luz.playerNumber!r}, a conta diz 3 (saiu {sai})"
        )
        for uniq, numero in esperado.items():
            if uniq != P4:
                assert bancada.o_que_acendeu(uniq)[:1] == [numero], (
                    f"{uniq}: {bancada.o_que_acendeu(uniq)}, a conta diz {numero}"
                )
