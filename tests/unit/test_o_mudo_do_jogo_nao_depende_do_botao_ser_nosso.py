"""O-MUDO-DO-JOGO-NAO-DEPENDE-DO-BOTAO-SER-NOSSO-01 — o pedido do jogo não é o botão.

A causa, medida no `807c8a6d7`: o `lifecycle.py` só chamava o
`hotkey.start_mic_hotkey` com `mic_button_toggles_system` ligado, e era ele
quem subia o `mic_do_jogo_loop` (o mudo que o jogo pede no `common[9]` do
vpad) e o `mic_da_mesa_loop` (as bordas do plástico com endereço). Com o
interruptor desligado no boot, o mudo do jogo não chegava ao controle do
jogador, e o aperto dela não derrubava a luz que o jogo pediu: a borda nunca
era publicada, e o laço da luz (que chama o `a_pessoa_mandou` em toda borda)
não tinha o que ler.

A cura: `start_mic_do_jogo` sobe as bordas e o mudo do jogo sempre; o
interruptor segura só a eleição (o `mic_button_loop`, que o consulta a cada
borda). Quem chama o `a_pessoa_mandou` com o interruptor desligado é o laço
da luz, pela mesma borda: nenhuma segunda leitura do botão.

A BANCADA: o `Daemon` de verdade com o `FakeController`, o laço de poll
trocado por um que publica no barramento o que o vpad e o plástico publicam.
Endereços da faixa forjada.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import hotkey, luz_do_mic
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from tests.unit.test_hotkey_mic_wire import _config_base, _make_state

#: P1 a P4, a mesma regra no cabo e no rádio: o laço lê o `uniq` do evento.
JOGADORES = tuple(f"aa:bb:cc:00:00:0{i}" for i in range(1, 5))


async def _rodar_com(
    daemon: Daemon, publicar: Any, *, ticks: int = 30, timeout: float = 8.0
) -> None:
    """Roda o daemon; no tique 5 chama ``publicar(daemon)``; para no fim."""

    async def _poll() -> None:
        tique = 0
        while not daemon._is_stopping():
            if tique == 5:
                publicar(daemon)
            if tique >= ticks:
                daemon.stop()
                break
            daemon.store.bump("poll.tick")
            tique += 1
            await asyncio.sleep(0.02)

    daemon._poll_loop = _poll  # type: ignore[method-assign]
    await asyncio.wait_for(daemon.run(), timeout=timeout)


@pytest.fixture(autouse=True)
def _limpo() -> Any:
    hotkey._MUDO_DO_JOGO.clear()
    luz_do_mic._LUZ_DO_JOGO.clear()
    luz_do_mic._A_PESSOA_MANDOU_EM.clear()
    yield
    hotkey._MUDO_DO_JOGO.clear()
    luz_do_mic._LUZ_DO_JOGO.clear()
    luz_do_mic._A_PESSOA_MANDOU_EM.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("ligado", [False, True], ids=["interruptor-desligado", "ligado"])
async def test_o_mudo_do_jogo_chega_ao_controle_de_cada_jogador(
    monkeypatch: pytest.MonkeyPatch, ligado: bool
) -> None:
    """O jogo cala o P1 e o P3 e abre o P2 e o P4: os quatro pedidos chegam.

    MORDIDA: devolver o gate (o `start_mic_do_jogo` dentro do `if` do
    interruptor no `lifecycle.py`) e o desligado reprova sem um pedido.
    """
    chegaram: list[tuple[str, bool]] = []

    async def _espiao(_daemon: Any, uniq: str, mudo: bool, _em: float) -> None:
        chegaram.append((uniq, mudo))

    monkeypatch.setattr(hotkey, "o_jogo_pede_o_mudo", _espiao)

    def _o_jogo_pede(daemon: Daemon) -> None:
        for n, uniq in enumerate(JOGADORES):
            daemon.bus.publish(
                EventTopic.MIC_DO_JOGO,
                {"uniq": uniq, "mudo": n % 2 == 0, "em": time.monotonic()},
            )

    fc = FakeController(states=[_make_state()])
    daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=ligado))
    await _rodar_com(daemon, _o_jogo_pede)

    esperado = sorted(
        (luz_do_mic.chave_do_mic(u) or "", n % 2 == 0) for n, u in enumerate(JOGADORES)
    )
    assert sorted(chegaram) == esperado, chegaram


class _BordasDoPlastico:
    """O ``bordas_do_mic`` do backend: o contador do aperto de cada controle."""

    def __init__(self) -> None:
        self.bordas: dict[str, tuple[int, bool, float | None]] = {}

    def __call__(self) -> dict[str, tuple[int, bool, float | None]]:
        return dict(self.bordas)


@pytest.mark.asyncio
async def test_com_o_interruptor_desligado_o_aperto_derruba_a_luz_do_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O jogo acendeu a luz do P2; ela aperta depois: vale o último que mandou.

    A borda nasce no backend (o contador do plástico), como na mesa dela, e o
    laço das bordas a publica; o laço da luz a lê e chama o `a_pessoa_mandou`.

    MORDIDA: as bordas fora do `start_mic_do_jogo` (de volta só com o
    interruptor) e a luz do jogo fica de pé depois do aperto.
    """
    from hefesto_dualsense4unix.daemon import lifecycle

    monkeypatch.setattr(lifecycle, "INPUT_GRACE_SEC", 0.0)
    uniq = JOGADORES[1]
    chave = luz_do_mic.chave_do_mic(uniq)
    assert chave is not None
    plastico = _BordasDoPlastico()
    plastico.bordas[uniq] = (0, False, None)

    def _jogo_e_aperto(_daemon: Daemon) -> None:
        antes = time.monotonic()
        assert luz_do_mic._o_jogo_pede_a_luz(chave, 1, antes)
        plastico.bordas[uniq] = (1, True, antes + 0.5)

    fc = FakeController(states=[_make_state()])
    fc.bordas_do_mic = plastico  # type: ignore[attr-defined]
    daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=False))
    await _rodar_com(daemon, _jogo_e_aperto)

    assert luz_do_mic.luz_do_mic_do_jogo(uniq) is None, "a luz do jogo ficou depois do aperto"
    assert luz_do_mic.quando_a_pessoa_mandou(uniq) is not None


@pytest.mark.asyncio
async def test_desligado_a_borda_nao_elege_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O interruptor segue valendo para o que é dele: a borda não vira ato."""
    atos: list[Any] = []

    async def _ato(*a: Any, **k: Any) -> None:
        atos.append((a, k))

    monkeypatch.setattr(hotkey, "ligar_o_microfone", _ato)

    def _aperto(daemon: Daemon) -> None:
        daemon.bus.publish(
            EventTopic.MIC_DA_MESA,
            {"uniq": JOGADORES[0], "mudo": False, "seq": 1, "em": time.monotonic()},
        )

    fc = FakeController(states=[_make_state()])
    daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=False))
    await _rodar_com(daemon, _aperto)
    assert atos == []
    nomes = {t.get_name() for t in daemon._tasks}
    assert "mic_button_loop" not in nomes
