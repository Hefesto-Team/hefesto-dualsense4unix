"""A luz do mic segue o botão quando não sabe quem ouve.

Sprint A-LUZ-DO-MIC-SEGUE-O-BOTAO-QUANDO-NAO-SABE-QUEM-OUVE-01. O contrato de
19/09 (D-O-BOTAO-DO-MIC-MANDA-NA-LUZ): aceso é o microfone LIGADO, haja ou não
app ouvindo. A lista de ouvintes só escolhe entre o `1` e o piscar; não saber
quem ouve não pode virar a luz do kernel (apagada, que ela lê «desligado»).

Quatro controles, P1 e P2 no cabo e P3 e P4 no rádio, com o laço de verdade e
dublês do backend e das peças irmãs.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as mod

P1 = "aabbcc0000a1"
P2 = "aabbcc0000a2"
P3 = "aabbcc0000a3"
P4 = "aabbcc0000a4"
OS_QUATRO = (P1, P2, P3, P4)
NO_CABO = (P1, P2)


class _Controle:
    """Backend dublado: as portas que o laço toca, e o transporte de cada um."""

    def __init__(self, mudo: dict[str, bool | None]) -> None:
        self.mudo = dict(mudo)
        self.escritas: list[tuple[str | None, int | None]] = []
        self.em_voo: list[tuple[str | None, int | None]] = []
        self.voltas = 0

    def set_microphone_led(self, aceso: Any, *, uniq: str | None = None) -> bool:
        self.escritas.append((uniq, aceso))
        return True

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        return None

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        valor = self.mudo.get(uniq or "")
        if valor is None:
            return None
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": valor}

    def describe_controllers(self) -> list[dict[str, object]]:
        self.voltas += 1
        return [
            {
                "index": i,
                "connected": True,
                "transport": "usb" if u in NO_CABO else "bt",
                "is_primary": i == 0,
                "uniq": u,
                "battery_pct": 90,
            }
            for i, u in enumerate(OS_QUATRO)
        ]

    def ultima(self, uniq: str, *, agora: bool = False) -> int | str | None:
        """A última escrita deste controle EM VOO (ou a de `agora`, no meio da corrida)."""
        do_uniq = [v for u, v in (self.escritas if agora else self.em_voo) if u == uniq]
        return do_uniq[-1] if do_uniq else "nenhuma"


class _Daemon:
    def __init__(self, controller: _Controle) -> None:
        self.bus = EventBus()
        self.controller = controller

    def _is_stopping(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


class _Medidor:
    """A PEÇA B com a forma real: `seguir` + `captando` + `parar`."""

    def __init__(self, captando: dict[str, bool]) -> None:
        self._captando = captando
        self.seguidos: list[str] = []

    def seguir(self, alvos: Any) -> None:
        self.seguidos = list(alvos)

    def captando(self) -> dict[str, bool]:
        return {u: v for u, v in self._captando.items() if u in self.seguidos}

    def parar(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "INTERVALO_S", 0.001)
    monkeypatch.setattr(mod, "INTERVALO_DE_QUEM_OUVE_S", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DO_REPORT_S", 0.001)
    monkeypatch.setattr(mod, "SEGURA_A_BORDA_S", 0.01)
    monkeypatch.setattr(mod, "SEM_RESPOSTA_ATE_SOLTAR_S", 0.05)
    monkeypatch.setattr(mod, "_fontes_para", lambda uniqs, _mesa: {u: f"fonte-{u}" for u in uniqs})
    mod._LUZ_DO_JOGO.clear()


def _pecas(monkeypatch: pytest.MonkeyPatch, ouvintes: Any, captando: dict[str, bool]) -> None:
    peca_a = types.ModuleType(mod.MODULO_DE_QUEM_OUVE)
    peca_a.quem_ouve_agora = ouvintes  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod.MODULO_DE_QUEM_OUVE, peca_a)
    medidor = _Medidor(captando)
    peca_b = types.ModuleType(mod.MODULO_DO_NIVEL)
    peca_b.NivelDoMicrofone = lambda: medidor  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod.MODULO_DO_NIVEL, peca_b)


async def _rodar(daemon: _Daemon, *, voltas: int, entre: Any = None) -> None:
    """Roda o laço e guarda em `em_voo` o que ele escreveu ANTES do cancelamento.

    O desligamento devolve a posse ao kernel de propósito (repinta e solta), e
    isso não é o laço soltando a luz no meio da sessão.
    """
    tarefa = asyncio.create_task(mod.luz_do_mic_loop(daemon))
    controle = daemon.controller
    try:
        while controle.voltas < voltas:
            await asyncio.sleep(0.002)
            if entre is not None:
                entre(controle.voltas)
        controle.em_voo = list(controle.escritas)
    finally:
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa


def _soltas(controle: _Controle, uniq: str) -> int:
    """Quantas vezes o laço devolveu a posse deste controle ao kernel em voo."""
    return sum(1 for u, v in controle.em_voo if u == uniq and v is None)


@pytest.mark.asyncio
async def test_o_pactl_caido_nao_apaga_a_luz_de_quem_esta_no_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PEÇA A responde `None` (o `pactl` caiu): os quatro no ar, luz acesa.

    Cada um aperta o botão (a posse é tomada); passado o prazo de soltura
    muitas vezes, a última escrita de cada um é `ACESA` e nenhum foi devolvido
    ao kernel, que pintaria a luz apagada sobre o microfone ligado.
    """
    controle = _Controle({u: False for u in OS_QUATRO})
    _pecas(monkeypatch, ouvintes=lambda _u: None, captando={})
    daemon = _Daemon(controle)
    apertados: set[str] = set()

    def apertar(voltas: int) -> None:
        for i, uniq in enumerate(OS_QUATRO):
            if voltas > 10 + 10 * i and uniq not in apertados:
                apertados.add(uniq)
                daemon.bus.publish(
                    str(EventTopic.MIC_DA_MESA), {"uniq": uniq, "mudo": False, "seq": i}
                )

    await _rodar(daemon, voltas=400, entre=apertar)

    assert apertados == set(OS_QUATRO)
    for uniq in OS_QUATRO:
        assert controle.ultima(uniq) == mod.ACESA, (
            f"{uniq}: microfone ligado com a lista desconhecida terminou em "
            f"{controle.ultima(uniq)!r}"
        )
        assert _soltas(controle, uniq) == 0, f"{uniq}: a posse voltou ao kernel"
        assert mod.estado_da_luz_do_mic(uniq) == mod.ACESA
        assert mod.quem_ouve_este_mic(uniq) is None, "a tela segue dizendo «não sei»"


@pytest.mark.asyncio
async def test_o_radio_sem_canal_acende_igual_ao_cabo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PEÇA A só conhece P1 e P2 (o rádio está em `sem_canal`).

    Sem aperto nenhum, os quatro acendem; um ouvinte no P1 com som entrando
    faz só o P1 piscar.
    """
    controle = _Controle({u: False for u in OS_QUATRO})
    quem: dict[str, list[str]] = {P1: [], P2: []}
    _pecas(monkeypatch, ouvintes=lambda _u: {u: list(v) for u, v in quem.items()},
           captando={P1: True})
    daemon = _Daemon(controle)
    vistas: dict[str, Any] = {}

    def ouvinte_no_p1(voltas: int) -> None:
        if voltas >= 100 and not vistas:
            vistas.update({u: controle.ultima(u, agora=True) for u in OS_QUATRO})
        if voltas > 120:
            quem[P1] = ["chrome"]

    await _rodar(daemon, voltas=300, entre=ouvinte_no_p1)

    assert vistas == {u: mod.ACESA for u in OS_QUATRO}, (
        f"antes do ouvinte, cabo e rádio divergem: {vistas!r}"
    )
    assert controle.ultima(P1) == mod.PISCANDO
    for uniq in (P2, P3, P4):
        assert controle.ultima(uniq) == mod.ACESA, f"{uniq} = {controle.ultima(uniq)!r}"
    for uniq in OS_QUATRO:
        assert _soltas(controle, uniq) == 0


@pytest.mark.parametrize("ouvintes", [None, [], ["chrome"]])
def test_o_mudo_apaga_e_o_mudo_desconhecido_nao_escreve(ouvintes: list[str] | None) -> None:
    """Mudo apaga com qualquer lista; sem o mudo dito, ninguém escreve."""
    assert mod.decidir(mudo=True, ouvintes=ouvintes, captando=True, bateria_pct=90) == mod.APAGADA
    assert mod.decidir(mudo=None, ouvintes=ouvintes, captando=True, bateria_pct=90) is None


@pytest.mark.asyncio
async def test_o_mudo_com_a_lista_desconhecida_apaga_no_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No laço: P3 (rádio) mudo com a PEÇA A caída apaga; P4 sem mudo dito, nada."""
    controle = _Controle({P1: False, P2: False, P3: True, P4: None})
    _pecas(monkeypatch, ouvintes=lambda _u: None, captando={})
    daemon = _Daemon(controle)

    await _rodar(daemon, voltas=100)

    assert controle.ultima(P3) == mod.APAGADA
    assert controle.ultima(P4) == "nenhuma"
    assert controle.ultima(P1) == mod.ACESA
