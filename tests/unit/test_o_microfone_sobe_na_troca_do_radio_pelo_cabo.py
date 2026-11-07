"""O microfone sobe na troca do rádio pelo cabo: a eleição espera o canal pelo evento.

O ensaio usa a eleição, o nascimento e o subsystem de verdade, sobre a lista de fontes de um `pactl`
de mentira em que o cartão de quem trocou chega depois do prazo de uma eleição.
"""

from __future__ import annotations

import asyncio
import importlib
import subprocess
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import bt_mic, hotkey
from hefesto_dualsense4unix.integrations import audio_control
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele
from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

P1 = "aa:bb:cc:00:00:a1"
P2 = "aa:bb:cc:00:00:b7"
P3 = "aa:bb:cc:00:00:c3"
P4 = "aa:bb:cc:00:00:d9"

MESAS: dict[str, tuple[tuple[str, str], ...]] = {
    "quatro-cabos": ((P1, "usb"), (P2, "usb"), (P3, "usb"), (P4, "usb")),
    "tres-e-um": ((P1, "usb"), (P2, "usb"), (P3, "usb"), (P4, "bluetooth")),
    "dois-e-dois": ((P1, "bluetooth"), (P2, "usb"), (P3, "usb"), (P4, "bluetooth")),
    "um-e-tres": ((P1, "bluetooth"), (P2, "bluetooth"), (P3, "bluetooth"), (P4, "usb")),
}


def _n(uniq: str) -> str:
    return norm_mac(uniq) or uniq


def _canal(uniq: str) -> str:
    return f"hefesto_mic_{_n(uniq)[-6:]}"


class _Som:
    """O servidor de som que a eleição vê: o cartão de cada controle nasce quando o ensaio diz."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, uniqs: list[str]) -> None:
        self.publicados = {_n(u): _canal(u) for u in uniqs}
        self.ativo: str | None = None
        self.leituras = 0
        monkeypatch.setattr(ele, "_rodar", self._rodar)
        monkeypatch.setattr(ele, "fonte_se_sustenta", lambda _nome: True)
        monkeypatch.setattr(ele, "outra_captura_elegivel", lambda: None)
        monkeypatch.setattr(ele, "casamento_usb_agora", lambda _uniqs: None)
        monkeypatch.setattr(ele, "SETTLE_PASSOS", 2)
        monkeypatch.setattr(ele, "SETTLE_PASSO_S", 0.0)
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSOS", 2)
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSO_S", 0.01)
        monkeypatch.setattr(audio_control, "fonte_de_captura_do_uniq", self._do_uniq)
        monkeypatch.setattr(audio_control, "volume_da_captura", lambda **_k: 100)
        monkeypatch.setattr(hotkey, "_fonte_esta_muda", lambda _fonte: False)
        monkeypatch.setattr(hotkey, "_microfone_que_ja_e_da_maquina", lambda: None)

    def _do_uniq(self, uniq: str, **_k: Any) -> str | None:
        return self.publicados.get(_n(uniq))

    def _rodar(self, argv: list[str]) -> tuple[int, str]:
        if argv[:2] == ["pactl", "get-default-source"]:
            return (0, self.ativo or "")
        if argv[:2] == ["pactl", "set-default-source"]:
            self.ativo = argv[2]
            return (0, "")
        if argv[:4] == ["pactl", "list", "sources", "short"]:
            self.leituras += 1
            return (
                0,
                "\n".join(
                    f"{i}\t{nome}\tmodule-pipe-source.c\ts16le 1ch 48000Hz\tSUSPENDED"
                    for i, nome in enumerate(self.publicados.values(), start=40)
                ),
            )
        raise AssertionError(f"pactl que esta régua não conhece: {argv}")


class _Backend:
    def __init__(self, mesa: tuple[tuple[str, str], ...]) -> None:
        self.mesa = mesa
        self.mudo = {_n(u): False for u, _ in mesa}

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True, "transport": t} for u, t in self.mesa]

    def audio_status_for(self, uniq: str | None = None) -> dict[str, Any]:
        return {"mic_mudo": self.mudo.get(_n(uniq or ""))}

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        if isinstance(muted, bool):
            self.mudo[_n(uniq or "")] = muted
        return True

    def set_mic_led(self, aceso: Any, *, uniq: str | None = None) -> None:
        del aceso, uniq


class _Daemon:
    def __init__(self, backend: _Backend) -> None:
        self.controller = backend
        self._tasks: list[Any] = []
        self.config = SimpleNamespace(mic_button_toggles_system=True)

    def _is_stopping(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


@pytest.fixture(autouse=True)
def _sem_processo_e_sem_espera_velha(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Sem processo e sem espera de outro teste.

    O módulo de quem ouve guarda o `_rodar` na importação: ele se importa antes do dublê entrar.
    """
    importlib.import_module("hefesto_dualsense4unix.integrations.quem_ouve_o_microfone")

    def _recusa(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"um teste desta régua tentou rodar processo: {args!r}")

    monkeypatch.setattr(subprocess, "run", _recusa)
    monkeypatch.setattr(subprocess, "Popen", _recusa)
    ele._QUEM_ESPERA_O_CANAL.clear()
    hotkey._CANAL_POR_UNIQ.clear()
    yield
    ele._QUEM_ESPERA_O_CANAL.clear()
    hotkey._CANAL_POR_UNIQ.clear()


def _montar(monkeypatch: pytest.MonkeyPatch, nome: str = "dois-e-dois") -> SimpleNamespace:
    mesa = MESAS[nome]
    som = _Som(monkeypatch, [u for u, _ in mesa])
    backend = _Backend(mesa)
    daemon = _Daemon(backend)
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal(), daemon=daemon)
    sub._backend = backend
    sub._gerenciador = SimpleNamespace(pontes={})
    anteriores = ele.registrar_dizedor_do_no_ar(
        sub.no_ar, sub.esquecer_a_palavra, sub.palavra_no_ar
    )
    pedidor = ele.registrar_pedidor_de_canal(sub.pedir_canal)
    return SimpleNamespace(
        som=som, sub=sub, daemon=daemon, anteriores=anteriores, pedidor=pedidor
    )


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> Any:
    m = _montar(monkeypatch)
    yield m
    ele.registrar_dizedor_do_no_ar(*m.anteriores)
    ele.registrar_pedidor_de_canal(m.pedidor)


async def _a_varredura_ve_o_canal(m: Any) -> None:
    m.sub._laco = asyncio.get_running_loop()
    m.sub._refazer_quem_esperava_o_canal()
    await asyncio.sleep(0)
    while hotkey._NASCIMENTOS_EM_VOO:
        await asyncio.gather(*list(hotkey._NASCIMENTOS_EM_VOO))


async def _a_troca(m: Any, uniq: str) -> bool:
    """O cabo entra: o controle volta à mesa e o cartão dele ainda não chegou ao servidor."""
    canal = m.som.publicados.pop(_n(uniq))
    nasceu = await hotkey.nascer_no_ar(m.daemon, uniq)
    m.som.publicados[_n(uniq)] = canal
    await _a_varredura_ve_o_canal(m)
    return nasceu


class TestOCartaoQueChegaDepoisDoPrazo:
    def test_a_eleicao_nao_desiste_e_o_canal_vira_o_padrao(self, mesa: Any) -> None:
        assert asyncio.run(_a_troca(mesa, P2)) is False, "o cartão não tinha chegado"
        assert mesa.som.ativo == _canal(P2), "o canal subiu e ninguém refez a eleição"
        assert hotkey._eleitor(mesa.daemon).eleito == P2

    def test_a_eleicao_devolve_o_fio_no_prazo(self, mesa: Any) -> None:
        mesa.som.publicados.pop(_n(P1))
        comeco = time.monotonic()
        ele.EleitorDeMicrofone().eleger_o_controle(P1, [P1, P2])
        assert time.monotonic() - comeco < 0.5
        assert ele.ha_quem_espere_o_canal()

    def test_o_cartao_que_nao_chega_nao_agenda_nada(self, mesa: Any) -> None:
        mesa.som.publicados.pop(_n(P1))
        ele.esperar_o_canal(P1)
        agendados: list[Any] = []

        async def _ensaio() -> None:
            mesa.sub._laco = asyncio.get_running_loop()
            original = hotkey.agendar_o_nascimento_do_microfone
            hotkey.agendar_o_nascimento_do_microfone = lambda *a, **k: agendados.append(a)
            try:
                mesa.sub._refazer_quem_esperava_o_canal()
                mesa.sub._refazer_quem_esperava_o_canal()
                await asyncio.sleep(0)
            finally:
                hotkey.agendar_o_nascimento_do_microfone = original

        asyncio.run(_ensaio())
        assert agendados == []
        assert ele.ha_quem_espere_o_canal()

    def test_a_eleicao_refeita_uma_vez_so(self, mesa: Any) -> None:
        async def _ensaio() -> int:
            await _a_troca(mesa, P2)
            escritas = mesa.som.leituras
            await _a_varredura_ve_o_canal(mesa)
            return mesa.som.leituras - escritas

        assert asyncio.run(_ensaio()) == 0
        assert not ele.ha_quem_espere_o_canal()

    def test_quem_saiu_da_mesa_para_de_esperar(self, mesa: Any) -> None:
        ele.esperar_o_canal(P1)
        ele.esperar_o_canal(P2)
        ele.esquecer_a_espera_de_quem_saiu(frozenset({_n(P2)}))
        assert set(ele._QUEM_ESPERA_O_CANAL) == {P2}

    def test_a_varredura_esquece_a_espera_de_quem_saiu(self, mesa: Any) -> None:
        mesa.sub.uniqs_na_mesa = lambda: frozenset({_n(P2)})
        ele.esperar_o_canal(P1)
        ele.esperar_o_canal(P2)
        mesa.sub._esquecer_quem_saiu_da_mesa([])
        assert set(ele._QUEM_ESPERA_O_CANAL) == {P2}

    def test_sem_ninguem_esperando_a_varredura_nao_pergunta_ao_servidor(self, mesa: Any) -> None:
        assert ele.consumir_quem_achou_o_canal() == []
        assert mesa.som.leituras == 0


class TestOEvento:
    def test_a_fonte_nova_acorda_a_espera_sem_dormir_o_passo(
        self, mesa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSOS", 4)
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSO_S", 1.0)
        canal = mesa.som.publicados.pop(_n(P1))

        def nasce() -> None:
            time.sleep(0.1)
            mesa.som.publicados[_n(P1)] = canal
            RETRATO._avisar(("sources",))

        threading.Thread(target=nasce, daemon=True).start()
        comeco = time.monotonic()
        fontes, _usb = ele.EleitorDeMicrofone()._canal_no_ar(P1, [P1, P2])
        assert canal in fontes
        assert time.monotonic() - comeco < 0.8, "a espera dormiu o passo, surda ao servidor"

    def test_a_rajada_do_servidor_nao_gasta_o_prazo(
        self, mesa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSOS", 4)
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSO_S", 0.1)
        mesa.som.publicados.pop(_n(P1))
        rajada = threading.Event()

        def trovoada() -> None:
            while not rajada.is_set():
                RETRATO._avisar(("sources",))
                time.sleep(0.001)

        threading.Thread(target=trovoada, daemon=True).start()
        comeco = time.monotonic()
        try:
            ele.EleitorDeMicrofone()._canal_no_ar(P1, [P1, P2])
        finally:
            rajada.set()
        assert time.monotonic() - comeco >= 0.35, "o cartão refeito gastou o prazo em eventos"

    def test_o_canal_nosso_so_acorda_a_varredura_com_quem_o_espera(
        self, mesa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        novidade = mesa.sub._registro.novidade
        ouvinte = threading.Thread(target=mesa.sub._ouvir_as_fontes, daemon=True)
        ouvinte.start()
        time.sleep(0.05)
        try:
            RETRATO._avisar(("sources",))
            assert novidade.wait(1.0)
            novidade.clear()
            RETRATO._avisar(("sources",))
            assert not novidade.wait(0.15), "canal nosso acordou a varredura sem ninguém esperar"
            ele.esperar_o_canal(P1)
            RETRATO._avisar(("sources",))
            assert novidade.wait(1.0), "quem espera o canal não ouviu o servidor"
        finally:
            mesa.sub._parar.set()
            RETRATO._avisar(("sources",))
            ouvinte.join(timeout=2.0)

    def test_a_varredura_de_verdade_refaz_quem_esperava(
        self, mesa: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(bt, "nos_dualsense_bluetooth", lambda: [])
        mesa.sub._gerenciador = SimpleNamespace(
            pontes={}, reconciliar=lambda _alvos: None, dormir=lambda _s: True
        )
        mesa.sub._registro.novidade.set()
        ele.esperar_o_canal(P2)

        async def _ensaio() -> None:
            mesa.sub._laco = asyncio.get_running_loop()
            await asyncio.to_thread(mesa.sub._loop)
            await asyncio.sleep(0)
            while hotkey._NASCIMENTOS_EM_VOO:
                await asyncio.gather(*list(hotkey._NASCIMENTOS_EM_VOO))

        asyncio.run(_ensaio())
        assert mesa.som.ativo == _canal(P2)

    def test_a_fonte_nova_acorda_a_varredura_sem_esperar_o_relogio(self, mesa: Any) -> None:
        novidade = mesa.sub._registro.novidade
        mesa.som.publicados.pop(_n(P1))
        ouvinte = threading.Thread(target=mesa.sub._ouvir_as_fontes, daemon=True)
        ouvinte.start()
        time.sleep(0.05)
        try:
            RETRATO._avisar(("sources",))
            assert novidade.wait(1.0)
            novidade.clear()
            mesa.som.publicados[_n(P1)] = "alsa_input.usb-Sony_DualSense-00.analog-stereo"
            RETRATO._avisar(("sources",))
            assert novidade.wait(1.0), "a placa nova esperou a varredura do relógio"
        finally:
            mesa.sub._parar.set()
            RETRATO._avisar(("sources",))
            ouvinte.join(timeout=2.0)

    def test_a_varredura_acorda_quando_o_recuo_do_pactl_vence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agora = [100.0]
        recuo = bt.RecuoDoPactl(relogio=lambda: agora[0])
        monkeypatch.setattr(bt, "PACTL", recuo)
        assert bt_mic._ate_a_proxima_varredura() == bt_mic.RECONCILIA_S
        recuo.estourou()
        agora[0] += 3.5
        assert bt_mic._ate_a_proxima_varredura() == pytest.approx(1.5)
        agora[0] += 2.0
        assert bt_mic._ate_a_proxima_varredura() == bt_mic.RECONCILIA_S


class TestOsQuatroJuntos:
    @pytest.mark.parametrize("arranjo", sorted(MESAS))
    @pytest.mark.parametrize("quem", [P1, P2, P3, P4], ids=["P1", "P2", "P3", "P4"])
    def test_a_troca_de_cada_um_com_os_outros_tres_na_mesa(
        self, monkeypatch: pytest.MonkeyPatch, arranjo: str, quem: str
    ) -> None:
        m = _montar(monkeypatch, arranjo)
        try:
            asyncio.run(_a_troca(m, quem))
            assert m.som.ativo == _canal(quem), "subiu o microfone de outro controle"
            assert hotkey._no_ar_da_sessao(m.daemon).esta(quem)
        finally:
            ele.registrar_dizedor_do_no_ar(*m.anteriores)
            ele.registrar_pedidor_de_canal(m.pedidor)

    @pytest.mark.parametrize("quem", [P1, P3, P4], ids=["P1", "P3", "P4"])
    def test_quem_troca_nao_toma_o_padrao_de_quem_o_tem(self, mesa: Any, quem: str) -> None:
        async def _ensaio() -> None:
            assert await hotkey.nascer_no_ar(mesa.daemon, P2)
            await _a_troca(mesa, quem)

        asyncio.run(_ensaio())
        assert mesa.som.ativo == _canal(P2)
        assert hotkey._no_ar_da_sessao(mesa.daemon).esta(quem)
        assert hotkey._no_ar_da_sessao(mesa.daemon).esta(P2)

    def test_dois_juntos_cada_um_com_o_seu_canal(self, mesa: Any) -> None:
        canais = {u: mesa.som.publicados.pop(_n(u)) for u in (P1, P2, P3, P4)}
        ele.esperar_o_canal(P3)
        ele.esperar_o_canal(P4)
        mesa.som.publicados[_n(P4)] = canais[P4]
        mesa.som.publicados[_n(P2)] = canais[P2]
        assert ele.consumir_quem_achou_o_canal() == [P4]
        assert ele.ha_quem_espere_o_canal()
        mesa.som.publicados[_n(P3)] = canais[P3]
        assert ele.consumir_quem_achou_o_canal() == [P3]
        assert not ele.ha_quem_espere_o_canal()
