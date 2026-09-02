"""A borda do botão de microfone, COM ENDEREÇO — e o que ela faz na mesa.

MIC-DA-MESA-ELEICAO-01 (01/09/2026). Este é o dono do *"quem apertou"*.

O PROBLEMA, e ele não é de preferência. O `hid-playstation` **consome** o botão
do microfone: a borda não vira evento evdev, o driver alterna `ds->mic_muted`
por conta própria e escreve o LED junto. Então não existe "botão do mic" com
endereço em lugar nenhum do produto:

* `EventTopic.BUTTON_DOWN` **não carrega `uniq`** — é contrato de perfil e de
  plugin, e dar-lhe um endereço quebraria os dois;
* `read_state()` só enxerga o PRIMÁRIO — numa mesa de quatro, três apertos
  ficariam sem dono.

O que existe é a CONSEQUÊNCIA do aperto: o bit `STATUS_MIC_MUDO` de `status[1]`,
que chega por um fd que é só daquele controle. **A identidade vem do fd, não do
report** — e é isso que `backend.bordas_do_mic()` devolve.

AS DUAS GUARDAS SÃO REUSADAS, NÃO REINVENTADAS. O sossego
(`hotkey.MIC_SOSSEGO_S`) e a carência pós-conexão (`lifecycle.INPUT_GRACE_SEC`)
existem por defeito medido. Escrever um debounce novo aqui criaria a segunda
régua sobre o mesmo estado, que é o defeito que esta casa já pagou onze vezes.

A JANELA DE SOSSEGO (MIC-REPIQUE-01, 19/08/2026) — a análise inteira, que
DESCEU DO `mic_button_loop` junto com a guarda, porque ela continua valendo
palavra por palavra e o que mudou foi só o laço onde a guarda mora.

O journal da noite de 18→19/08 tem três `mic_hotkey_toggle` em 2,5 s às
01:52:27 — `muted=False`, `muted=True`, `muted=False`. Isso não é mão humana, e
o produto não tinha defesa nenhuma: toda a proteção estava terceirizada para o
debounce de 200 ms do `AudioControl`, que é inútil aqui por três motivos, cada
um verificável no fonte:

1. **O relógio dele começa no INÍCIO da chamada**
   (`integrations/audio_control.py`: `self._last_call_at = now` é gravado ANTES
   dos subprocessos). Como a chamada roda `wpctl`/`pactl` com `timeout=2.0`,
   ela pode levar segundos — e quando termina o debounce já expirou faz tempo.
   A janela efetiva é ``max(0, 0.2 - duração)``, ou seja: ZERO sempre que o
   áudio demora.
2. **Ele protege a coisa errada.** 200 ms é medida de teclinha repicando; do
   outro lado está um estado LATCHED do sistema inteiro, invisível para quem
   está de controle na mão dentro de um jogo.
3. **Ele não sabe de onde vieram as bordas.** Esta casa já documentou o
   **micBtn fantasma** ao (re)conectar (`INPUT_GRACE_SEC`) e já pegou áudio do
   próprio microfone sendo lido como estado de botão (commit `702f5b6`).

A guarda daqui não precisa saber qual das fontes disparou: ela é contada a
partir do último gesto ACEITO e engole tudo que chegar dentro de
`MIC_SOSSEGO_S`. O preço de um falso engolir é um toque ignorado — visível e
refazível num segundo; o preço de um falso gesto era a usuária muda no jogo sem
saber, e passa a ser o microfone do sistema trocando sozinho.

**O QUE MUDOU NA GUARDA, e é por causa do endereço:** o sossego passou a ser
POR CONTROLE. Ele era um relógio SÓ porque o gesto era um só (o mudo do
sistema); com quatro na mesa, uma janela global faria dois jogadores que
apertam junto virarem um gesto, e o do segundo sumiria calado.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:  # pragma: no cover - só para tipo
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

#: Cadência da varredura das bordas. Não é polling de DADO: o contador vive no
#: handle e sobe sozinho na thread de leitura dele; isto só pergunta "subiu?".
#: 20 Hz é a metade da janela de sossego — perto o bastante para o gesto dela
#: parecer imediato, e longe o bastante para não custar nada.
INTERVALO_S: float = 0.05


def _bordas(backend: Any) -> dict[str, tuple[int, bool, float | None]]:
    """`backend.bordas_do_mic()` quando o backend sabe responder; `{}` senão.

    `getattr` porque nem todo backend é o de produção — os dublês da suíte e o
    backend de um controle só não conhecem a pergunta, e um backend que não
    conhece a pergunta não pode virar portão silencioso.
    """
    ler = getattr(backend, "bordas_do_mic", None)
    if not callable(ler):
        return {}
    try:
        valor = ler()
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("mic_da_mesa_leitura_falhou", err=str(exc))
        return {}
    return valor if isinstance(valor, dict) else {}


async def mic_da_mesa_loop(daemon: DaemonProtocol) -> None:
    """Vê as bordas por `uniq`, aplica as guardas, publica `MIC_DA_MESA`.

    Este laço **não escreve nada**: ele só dá endereço ao gesto. Quem elege é
    `integrations/eleicao_de_microfone.py` e quem acende é
    `backend.set_mic_led(..., uniq=)` — separados de propósito, porque a
    eleição toca no áudio da máquina dela e tem de poder ser recusada sem que
    a leitura do gesto se perca.

    A PRIMEIRA VARREDURA NÃO DISPARA NADA, e isso é a carência: quando o laço
    começa (ou quando um controle chega), o contador daquele `uniq` já pode
    estar em qualquer número — tratá-lo como "borda nova" seria eleger no
    hotplug, que é literalmente o micBtn fantasma com outro nome.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import INPUT_GRACE_SEC
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import MIC_SOSSEGO_S

    relogio = asyncio.get_running_loop().time
    visto: dict[str, int] = {}
    ultimo_por_uniq: dict[str, float] = {}
    nasceu_em = relogio()
    repiques = 0
    while not daemon._is_stopping():
        await asyncio.sleep(INTERVALO_S)
        backend = getattr(daemon, "controller", None)
        if backend is None:
            continue
        agora = relogio()
        atual = _bordas(backend)
        # Controle que saiu da mesa perde a memória do contador: quando voltar,
        # o handle é NOVO e o `seq` dele recomeça do zero. Guardar o número
        # velho faria a primeira borda depois da reconexão parecer um retrocesso
        # (e a próxima, um salto) — dois erros pelo preço de um.
        for uniq in list(visto):
            if uniq not in atual:
                visto.pop(uniq, None)
                ultimo_por_uniq.pop(uniq, None)
        for uniq, (seq, mudo, _quando) in atual.items():
            anterior = visto.get(uniq)
            visto[uniq] = seq
            if anterior is None or seq == anterior:
                # Primeira vez que vemos este controle: só adotamos o número.
                continue
            if (agora - nasceu_em) < INPUT_GRACE_SEC:
                logger.debug("mic_da_mesa_carencia", uniq=uniq)
                continue
            desde = agora - ultimo_por_uniq.get(uniq, float("-inf"))
            if desde < MIC_SOSSEGO_S:
                repiques += 1
                logger.debug(
                    "mic_da_mesa_repique_engolido", uniq=uniq, desde_s=round(desde, 3)
                )
                continue
            ultimo_por_uniq[uniq] = agora
            logger.info(
                "mic_da_mesa_borda",
                uniq=uniq,
                mudo=mudo,
                seq=seq,
                repiques_engolidos=repiques,
            )
            repiques = 0
            daemon.bus.publish(
                _TOPICO, {"uniq": uniq, "mudo": mudo, "seq": seq}
            )


def start_mic_da_mesa(daemon: DaemonProtocol) -> None:
    """Sobe o laço das bordas. Idempotente do ponto de vista do chamador."""
    task = asyncio.create_task(mic_da_mesa_loop(daemon), name="mic_da_mesa_loop")
    daemon._tasks.append(task)
    logger.info("mic_da_mesa_iniciado")


def _topico() -> str:
    from hefesto_dualsense4unix.core.events import EventTopic

    return str(EventTopic.MIC_DA_MESA)


_TOPICO = _topico()


__all__ = ["INTERVALO_S", "mic_da_mesa_loop", "start_mic_da_mesa"]
