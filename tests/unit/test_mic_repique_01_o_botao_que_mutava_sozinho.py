"""MIC-REPIQUE-01 e MIC-DOIS-DONOS-01 — o microfone mudo dentro do jogo.

Noite de 18→19/08/2026. Ela não conseguia jogar, e quando o controle enfim
funcionou o microfone estava mudo DENTRO do jogo. O que foi medido por fora:

* a fonte padrão do sistema É o microfone do DualSense, ``Mute: não``,
  volume 95% — ou seja, a camada do PipeWire estava ABERTA;
* o journal do daemon tem três ``mic_hotkey_toggle`` em 2,5 segundos às
  01:52:27 — ``muted=False``, ``muted=True``, ``muted=False``. Isso não é mão
  humana.

Os dois testes deste arquivo cobrem os dois defeitos de código que explicam
esse par de fatos, e nenhum dos dois precisa saber de onde vieram as bordas:

**(A) O laço do botão não tinha defesa nenhuma contra rajada.** Toda a
proteção estava terceirizada para o debounce de 200 ms do ``AudioControl``, e
esse debounce grava o relógio ANTES de rodar dois subprocessos com
``timeout=2.0`` cada — a janela efetiva é ``max(0, 0.2 - duração)``, isto é,
ZERO sempre que o áudio demora. Rajada de bordas virava rajada de toggles.

**(B) Um toque no botão move DOIS mudos, e ninguém os apresentava.** O
``hid-playstation`` alterna o mudo do FIRMWARE na borda do botão físico (está
escrito em ``core/backend_pydualsense.py:421``, em ``set_microphone_mute`` e
em ``docs/protocol/ipc-unix-socket.md``), e o ``mic_button_loop`` alterna o
mudo do SISTEMA na MESMA borda. Dois mudos em série: o som só passa com os
dois abertos. Um número ÍMPAR de bordas — três, como no journal — deixa os
dois em fase oposta, e é exatamente esse o retrato que ela mediu: ``pactl``
respondendo ``Mute: não`` com o microfone morto no jogo.

Hipótese vs. medição, para quem vier depois: que houve três toggles é
MEDIDO (journal); que o firmware ficou mudo enquanto o sistema ficou aberto é
HIPÓTESE — coerente com tudo que foi medido, e é a única que explica
``Mute: não`` com o jogo sem áudio. A cura não depende da hipótese: alinhar as
duas camadas e engolir a rajada torna o estado divergente impossível de
produzir, e a leitura de volta o torna visível no journal se ainda assim
acontecer.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import hotkey as mod

# ---------------------------------------------------------------------------
# Dublês mínimos — o alvo é o laço, não o daemon inteiro
# ---------------------------------------------------------------------------


class _Config:
    def __init__(self, *, mic_button_toggles_system: bool = True) -> None:
        self.mic_button_toggles_system = mic_button_toggles_system


class _Audio:
    """AudioControl dublado: alterna e conta, sem tocar em subprocess."""

    def __init__(self) -> None:
        self.mudo = False
        self.toggles = 0

    def toggle_default_source_mute(self) -> bool:
        self.toggles += 1
        self.mudo = not self.mudo
        return self.mudo


class _Controle:
    """Controle dublado com as três chamadas de microfone do caminho."""

    def __init__(self, *, declara: bool | None = None) -> None:
        self.leds: list[bool] = []
        self.firmware: list[bool | None] = []
        self._declara = declara

    def set_mic_led(self, muted: bool) -> None:
        self.leds.append(bool(muted))

    def set_microphone_mute(self, muted: bool | None) -> bool:
        self.firmware.append(muted)
        return True

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        del uniq
        if self._declara is None:
            return None
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": self._declara}


class _ControleSemFirmware:
    """Backend antigo: só sabe acender o LED do microfone."""

    def __init__(self) -> None:
        self.leds: list[bool] = []

    def set_mic_led(self, muted: bool) -> None:
        self.leds.append(bool(muted))


class _Daemon:
    def __init__(self, *, controller: Any, config: _Config) -> None:
        self.bus = EventBus()
        self.config = config
        self.controller = controller
        self._audio = _Audio()
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


async def _tocar_botao(daemon: _Daemon, vezes: int) -> None:
    """Publica `vezes` bordas de BUTTON_DOWN do mic_btn, uma atrás da outra."""
    for _ in range(vezes):
        daemon.bus.publish(EventTopic.BUTTON_DOWN, {"button": "mic_btn", "pressed": True})
        await asyncio.sleep(0)


async def _rodar(daemon: _Daemon, corpo: Any) -> None:
    """Sobe o laço, roda `corpo`, deixa assentar e derruba o laço."""
    tarefa = asyncio.create_task(mod.mic_button_loop(daemon))
    await asyncio.sleep(0)  # deixa o laço subscrever antes de publicar
    try:
        await corpo(daemon)
        for _ in range(60):  # deixa o laço drenar tudo que ficou na fila
            await asyncio.sleep(0.005)
    finally:
        daemon._parando = True
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa


# ---------------------------------------------------------------------------
# (A) A rajada
# ---------------------------------------------------------------------------


class TestARajadaDeBordas:
    @pytest.mark.asyncio
    async def test_cinco_bordas_seguidas_viram_um_toggle_so(self) -> None:
        """O defeito de 01:52:27: N bordas viravam N toggles do mudo do sistema.

        ARRANQUE A CURA (a checagem de `MIC_SOSSEGO_S` em `mic_button_loop`) e
        este teste reprova com `toggles == 5`: cada borda mexendo no mudo do
        sistema inteiro, sem ninguém para ver.
        """
        daemon = _Daemon(controller=_Controle(), config=_Config())

        await _rodar(daemon, lambda d: _tocar_botao(d, 5))

        assert daemon._audio.toggles == 1, (
            "uma rajada de bordas tem de virar UM toggle — o mudo do sistema é "
            "latched e invisível para quem está de controle na mão"
        )
        assert daemon._audio.mudo is True
        assert daemon.controller.leds == [True]

    @pytest.mark.asyncio
    async def test_o_botao_continua_funcionando_passada_a_janela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guarda não pode matar o botão: passado o sossego, ele alterna de novo."""
        monkeypatch.setattr(mod, "MIC_SOSSEGO_S", 0.02)
        daemon = _Daemon(controller=_Controle(), config=_Config())

        async def corpo(d: _Daemon) -> None:
            await _tocar_botao(d, 1)
            await asyncio.sleep(0.1)
            await _tocar_botao(d, 1)

        await _rodar(daemon, corpo)

        assert daemon._audio.toggles == 2
        assert daemon._audio.mudo is False, "mutou e desmutou — voltou ao aberto"
        assert daemon.controller.leds == [True, False]


# ---------------------------------------------------------------------------
# (B) Os dois donos do mudo
# ---------------------------------------------------------------------------


# MIC-DOIS-DONOS-01 — a classe `TestOsDoisDonosDoMudo` foi REMOVIDA em 19/08/2026,
# junto com a cura que ela testava. NÃO a reponha.
#
# A LEITURA continua certa e vale registrar: um toque no botão de microfone move
# DOIS mudos — o do FIRMWARE, que o `hid-playstation` alterna na borda do botão
# físico, e o do SISTEMA, que este laço alterna na mesma borda. Em série, o
# microfone só passa quando os dois estão abertos, e um número ímpar de bordas
# que um vê e o outro não os deixa em fase oposta. Foi assim que, na noite de
# 18->19/08, o `pactl` respondia `Mute: não`, o medidor da aba Status desenhava
# nível, e o jogo não recebia nada.
#
# A CURA proposta — afirmar o mudo do firmware junto com o do sistema — está
# RECUSADA por decisão medida, e a recusa é anterior:
#
#   * escrever no registrador do firmware TOMA A POSSE, e o botão físico dela
#     para de valer — recusado por escrito na BT-E-VPAD-01 (medido 01/08),
#     reafirmado na MIC-BT-DONO-01 (03/08), na linha `audio.microfone.mudo` do
#     mapa de canais, e no `controller_card.py`, que chama isso de "sequestro
#     silencioso que esta sprint foi fechar";
#   * no rádio a posse EVAPORA (medido 03/08: mudo = 100% -> 46% -> 100%), porque
#     `_mic_mute_desejado` é atributo de instância de um handle que morre a cada
#     reconexão;
#   * em co-op escreveria no controle ERRADO: o `BUTTON_DOWN` não carrega `uniq`,
#     então o jogador 2 mutaria o firmware do jogador 1.
#
# O que sobrou de pé, e é o que este arquivo testa: a janela de sossego contra a
# rajada de bordas (`TestARajadaDeBordas`).
