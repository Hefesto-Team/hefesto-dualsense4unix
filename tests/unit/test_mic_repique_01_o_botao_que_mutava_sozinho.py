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


async def _rodar_bordas(daemon: _Daemon, corpo: Any) -> None:
    """Sobe o laço das BORDAS, roda `corpo`, deixa drenar e derruba o laço."""
    from hefesto_dualsense4unix.daemon.subsystems import mic_da_mesa

    tarefa = asyncio.create_task(mic_da_mesa.mic_da_mesa_loop(daemon))
    try:
        await corpo(daemon)
        for _ in range(60):
            await asyncio.sleep(0.005)
    finally:
        daemon._parando = True
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa


# ---------------------------------------------------------------------------
# (A) A rajada — agora COM ENDEREÇO (MIC-DA-MESA-ELEICAO-01)
# ---------------------------------------------------------------------------
#
# O SOSSEGO MUDOU DE CASA, e o motivo é o eixo do gesto. Ele vivia no
# `mic_button_loop`, que consumia `BUTTON_DOWN` e alternava o mudo do sistema.
# Desde 01/09/2026 o botão ELEGE em vez de mutar, e a borda com endereço nasce
# em `daemon/subsystems/mic_da_mesa.py` — que é onde a guarda tem de estar,
# porque é lá que a borda existe. Duas réguas sobre o mesmo estado é o defeito
# que esta casa já pagou onze vezes.
#
# O QUE NÃO MUDOU: N bordas em rajada continuam tendo de virar UMA. O preço de
# engolir um toque de verdade é um gesto refeito em um segundo; o preço de um
# falso gesto era a usuária muda no jogo sem saber, e passa a ser o microfone
# do sistema trocando sozinho.


class _BackendComBordas:
    """Backend dublado: `bordas_do_mic()` com contador que o teste move."""

    def __init__(self, uniqs: tuple[str, ...]) -> None:
        self._seq = dict.fromkeys(uniqs, 0)
        self._mudo = dict.fromkeys(uniqs, False)

    def apertar(self, uniq: str) -> None:
        self._seq[uniq] += 1
        self._mudo[uniq] = not self._mudo[uniq]

    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None]]:
        return {u: (self._seq[u], self._mudo[u], None) for u in self._seq}


_P1 = "aabbcc000001"
_P2 = "aabbcc000002"


class TestARajadaDeBordas:
    @pytest.mark.asyncio
    async def test_cinco_bordas_seguidas_viram_uma_eleicao_so(self) -> None:
        """O defeito de 01:52:27, no eixo novo: N bordas viravam N gestos.

        ARRANQUE A CURA (a checagem de `MIC_SOSSEGO_S` em `mic_da_mesa_loop`) e
        este teste reprova com cinco eventos — cinco eleições do microfone do
        sistema numa rajada, sem ninguém para ver.
        """
        backend = _BackendComBordas((_P1,))
        daemon = _Daemon(controller=backend, config=_Config())
        fila = daemon.bus.subscribe(EventTopic.MIC_DA_MESA)

        async def corpo(d: _Daemon) -> None:
            await asyncio.sleep(0.4)  # passa a carência pós-conexão (0,3 s)
            for _ in range(5):
                backend.apertar(_P1)
                await asyncio.sleep(0.06)

        await _rodar_bordas(daemon, corpo)

        assert fila.qsize() == 1, (
            "uma rajada de bordas tem de virar UM gesto — o microfone padrão do "
            "sistema é latched e invisível para quem está de controle na mão"
        )
        assert fila.get_nowait()["uniq"] == _P1

    @pytest.mark.asyncio
    async def test_o_botao_continua_funcionando_passada_a_janela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guarda não pode matar o botão: passado o sossego, ele age de novo."""
        monkeypatch.setattr(mod, "MIC_SOSSEGO_S", 0.02)
        backend = _BackendComBordas((_P1,))
        daemon = _Daemon(controller=backend, config=_Config())
        fila = daemon.bus.subscribe(EventTopic.MIC_DA_MESA)

        async def corpo(d: _Daemon) -> None:
            await asyncio.sleep(0.4)  # a carência pós-conexão (0,3 s)
            backend.apertar(_P1)
            await asyncio.sleep(0.15)
            backend.apertar(_P1)

        await _rodar_bordas(daemon, corpo)

        assert fila.qsize() == 2
        assert fila.get_nowait()["mudo"] is True
        assert fila.get_nowait()["mudo"] is False

    @pytest.mark.asyncio
    async def test_o_sossego_e_por_controle_e_nao_da_mesa(self) -> None:
        """Numa mesa de quatro, o Jogador 2 não engole o gesto do Jogador 1.

        A guarda velha era um relógio SÓ, porque o gesto velho era um só (o mudo
        do sistema). Com endereço, uma janela global faria dois jogadores que
        apertam junto virarem um gesto — e o do segundo sumiria calado.
        """
        backend = _BackendComBordas((_P1, _P2))
        daemon = _Daemon(controller=backend, config=_Config())
        fila = daemon.bus.subscribe(EventTopic.MIC_DA_MESA)

        async def corpo(d: _Daemon) -> None:
            await asyncio.sleep(0.4)  # a carência pós-conexão (0,3 s)
            backend.apertar(_P1)
            backend.apertar(_P2)
            await asyncio.sleep(0.1)

        await _rodar_bordas(daemon, corpo)

        assert fila.qsize() == 2
        vistos = {fila.get_nowait()["uniq"] for _ in range(2)}
        assert vistos == {_P1, _P2}

    @pytest.mark.asyncio
    async def test_a_borda_dentro_da_carencia_nao_vira_gesto(self) -> None:
        """A CARÊNCIA PÓS-CONEXÃO, medida — e ela não tinha régua nenhuma.

        ACHADO DA AUDITORIA DE 02/09/2026. O laço novo aplica o mesmo
        `INPUT_GRACE_SEC` que curou o micBtn fantasma do hotplug — o defeito que
        fez um controle dela ser DESLIGADO —, e ninguém o guardava: arrancada a
        linha inteira de `daemon/subsystems/mic_da_mesa.py`, 859 réguas de
        mic/áudio/hotkey ficaram verdes.

        E havia um PONTEIRO FALSO no repositório: o docstring de
        `test_daemon_connect_grace.py` afirmava que "o teste da carência lá é
        `TestARajadaDeBordas`". Os três testes desta classe começavam com
        `await asyncio.sleep(0.4)`, que PASSA POR CIMA da carência de 0,3 s.
        Nenhum apertava dentro dela. Este aperta.

        As duas metades, porque uma cura que mata o botão não é cura: a borda
        DENTRO da carência não vira gesto, e o mesmo botão volta a valer depois.

        CURA A ARRANCAR: a checagem `(agora - nasceu_em) < INPUT_GRACE_SEC` do
        `mic_da_mesa_loop` — esta régua reprova com o gesto fantasma.
        """
        backend = _BackendComBordas((_P1,))
        daemon = _Daemon(controller=backend, config=_Config())
        fila = daemon.bus.subscribe(EventTopic.MIC_DA_MESA)

        dentro: list[int] = []

        async def corpo(d: _Daemon) -> None:
            # A carência é 0,3 s e o laço varre a cada 0,05 s: apertar aos
            # 0,10 s dá ao laço duas varreduras — a que adota o contador e a
            # que vê a borda — as duas dentro da janela.
            await asyncio.sleep(0.10)
            backend.apertar(_P1)
            await asyncio.sleep(0.15)
            dentro.append(fila.qsize())
            # E agora, PASSADA a carência, o mesmo botão tem de valer.
            await asyncio.sleep(0.35)
            backend.apertar(_P1)
            await asyncio.sleep(0.15)

        await _rodar_bordas(daemon, corpo)

        assert dentro == [0], (
            "uma borda DENTRO da carência pós-conexão virou gesto — é o micBtn "
            "fantasma do hotplug com outro nome, e desta vez ele troca o "
            f"microfone padrão do sistema: fila com {dentro}"
        )
        assert fila.qsize() == 1, (
            "passada a carência o botão tem de voltar a valer — uma guarda que "
            "mata o gesto não é guarda"
        )


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
