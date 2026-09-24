"""Subsystem de poll loop — leitura de estado do controle e publicação de eventos.

Responsabilidades:
  - Ler estado do IController a cada 1/poll_hz segundos.
  - Publicar STATE_UPDATE, BATTERY_CHANGE, BUTTON_DOWN, BUTTON_UP no EventBus.
  - Chamar _reassert_rumble a cada 200ms.
  - Despachar eventos para mouse e hotkey_manager (via referência no Daemon).
  - Reconectar automaticamente em caso de falha de leitura.

Nota: este módulo implementa Subsystem mas também expõe BatteryDebouncer
e as constantes de debounce que são importadas por testes externos.
"""
from __future__ import annotations

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

BATTERY_DEBOUNCE_SEC = 5.0
BATTERY_MIN_INTERVAL_SEC = 0.1
BATTERY_DELTA_THRESHOLD_PCT = 1


class BatteryDebouncer:
    """Debounce de eventos de bateria (V2-17 + ADR-008).

    Dispara se:
      - nunca disparou (primeiro valor); ou
      - abs(delta_pct) >= BATTERY_DELTA_THRESHOLD_PCT (e respeita min interval); ou
      - elapsed_since_last_emit >= BATTERY_DEBOUNCE_SEC.

    Sempre respeita BATTERY_MIN_INTERVAL_SEC entre disparos consecutivos.
    """

    def __init__(self) -> None:
        self.last_emitted_value: int | None = None
        self.last_emit_at: float = 0.0

    def should_emit(self, value: int, now: float) -> bool:
        if self.last_emitted_value is None:
            return True
        interval = now - self.last_emit_at
        if interval < BATTERY_MIN_INTERVAL_SEC:
            return False
        delta = abs(value - self.last_emitted_value)
        return delta >= BATTERY_DELTA_THRESHOLD_PCT or interval >= BATTERY_DEBOUNCE_SEC

    def mark_emitted(self, value: int, now: float) -> None:
        self.last_emitted_value = value
        self.last_emit_at = now


def evdev_buttons_once(daemon: object) -> frozenset[str]:
    """Snapshot dos botões físicos via evdev — chamado 1x por tick no poll loop.

    Retorna frozenset vazio se evdev não está disponível ou falha.
    Exceções são logadas em debug para não poluir logs de produção.
    """
    evdev = getattr(getattr(daemon, "controller", None), "_evdev", None)
    if evdev is None or not evdev.is_available():
        return frozenset()
    try:
        return frozenset(evdev.snapshot().buttons_pressed)
    except Exception as exc:
        logger.debug("evdev_snapshot_falhou", err=str(exc))
        return frozenset()


# --- os atalhos do PS na espera do lugar guardado (OS-ATALHOS-NA-ESPERA-01) --
#
# MORA DEPOIS DO `evdev_buttons_once` de propósito: o mapa de canais
# (`docs/data/mapa-controles.csv`) cita aquela função por linha (`:53-66`), e
# nada acima dela se mexe.

#: O atributo do daemon em que fica QUEM segura os atalhos durante a vaga (o
#: MAC do próximo da fila), para o diário dizer a troca de mão uma vez por
#: episódio, e não a cada tique. None = os atalhos estão com o dono do posto.
_MAO_DOS_ATALHOS = "_atalhos_na_mao_de"


def observar_os_atalhos(
    daemon: object, buttons_pressed: frozenset[str], *, now: float
) -> str | None:
    """Entrega ao `HotkeyManager` os botões de QUEM SEGURA os atalhos do PS.

    Chamado pelo `_poll_loop` a cada tique, no lugar em que ele chamava o
    `observe` com os botões do primário. Devolve o que o `observe` devolve (o
    nome do gesto que disparou, ou None), e None sem gerente de atalhos.

    `buttons_pressed` continua sendo o que o laço leu do leitor do primário
    (`evdev_buttons_once`) e mandou ao vpad do P1 — esta função não o muda
    para ninguém além dos atalhos.
    """
    gerente = getattr(daemon, "_hotkey_manager", None)
    if gerente is None:
        return None
    resultado: str | None = gerente.observe(
        botoes_dos_atalhos(daemon, buttons_pressed), now=now
    )
    return resultado


def botoes_dos_atalhos(daemon: object, botoes_do_posto: frozenset[str]) -> frozenset[str]:
    """Os botões que os atalhos do PS leem neste tique.

    **A DECISÃO É DELA** (24/09/2026, 19h, `D-2409-OS-ATALHOS-NA-ESPERA-FICAM-
    COM-O-P2`): *«O P2 segura os atalhos durante a espera, sem trocar de
    número»*, e quando o P1 volta, os atalhos voltam para ele. Revoga o «custo
    aceito» da `D-2409-O-JOGO-ESPERA-O-LUGAR-GUARDADO`.

    O DEFEITO, medido com a classe real (a bancada de queda): com o jogo aberto
    e o P1 fora dentro do prazo, o posto de P1 fica VAGO (o backend,
    `_quem_senta_no_posto`), o leitor do primário não tem nó, e este tique
    devolvia `frozenset()` por até 30 s — nenhum atalho do PS disparava, de
    controle nenhum. Antes da O-ASSENTO-GUARDADO-NAO-ANDA-02, o P2 virava
    primário na hora e ganhava os atalhos junto com o boneco 1.

    Fora da vaga, devolve `botoes_do_posto` intocado: o custo é um `getattr`
    e uma comparação. Na vaga, devolve os do próximo da fila que está na mesa
    (:func:`quem_segura_os_atalhos`) — os botões que ele já manda ao vpad
    DELE, lidos pelo mesmo leitor do co-op. O vpad do P1 continua parado: o
    laço manda a ele `botoes_do_posto`, nunca estes.
    """
    proximo = _o_proximo_da_fila(daemon)
    _anotar_a_mao(daemon, proximo[0] if proximo is not None else None)
    return botoes_do_posto if proximo is None else proximo[1]


def quem_segura_os_atalhos(daemon: object) -> str | None:
    """O MAC de quem segura os atalhos do PS agora — o DONO ÚNICO da pergunta.

    O dono do posto de P1 (`primary_uniq`); na vaga do posto, o próximo da
    fila que está na mesa. None quando não há de quem perguntar (sem
    controle, backend sem MAC).

    Quem precisa saber de QUEM é o gesto pergunta aqui, e não ao
    `primary_uniq`: o PS + L3 anda o cartão de quem o faz
    (`hotkey.build_next_mask_callback`). Uma segunda resposta deixaria os
    botões de um controle andando o cartão de outro — na vaga, o do P1
    ausente, cujo vpad parado o jogo perderia ao ser recriado (a R-04).
    """
    proximo = _o_proximo_da_fila(daemon)
    if proximo is not None:
        return proximo[0]
    uniq = getattr(getattr(daemon, "controller", None), "primary_uniq", None)
    return uniq if isinstance(uniq, str) and uniq else None


def _o_proximo_da_fila(daemon: object) -> tuple[str, frozenset[str]] | None:
    """Na vaga do posto de P1: `(MAC, botões)` do próximo da fila na mesa. Fora dela, None.

    **A VAGA É DO BACKEND**, e a pergunta é a MESMA que o `read_state` faz no
    mesmo tique (`_posto_vago_de`): é ela que para o vpad do P1, e os atalhos
    mudam de mão exatamente quando ele para. Refazer a conta aqui (o prazo, o
    jogo com a autoridade, o co-op de pé) seria um segundo dono da vaga.

    **O PRÓXIMO DA FILA** é o jogador do co-op com o MENOR número da lâmpada
    (`CoopManager.numeros_de_jogador`, a fonte única do número que ele vê no
    próprio controle) entre os que estão na mesa com o vpad de pé
    (`CoopManager.live_snapshots`, que já deixa de fora quem saiu, quem
    espera o grab e quem não tem MAC). Na vaga ninguém troca de número: é o
    P2; se o P2 também saiu, o P3; se o P3 também, o P4. O dono do posto
    nunca entra na conta — ele é quem está fora.

    Nunca levanta: um co-op que falha aqui deixa os atalhos com o posto neste
    tique, e o laço segue.
    """
    controller = getattr(daemon, "controller", None)
    if not isinstance(getattr(controller, "_posto_vago_de", None), str):
        return None
    coop = getattr(daemon, "_coop_manager", None)
    if coop is None:
        return None
    try:
        vivos = coop.live_snapshots()
        numeros = coop.numeros_de_jogador()
    except Exception as exc:
        logger.debug("atalhos_na_vaga_sem_fila", err=str(exc))
        return None
    if not isinstance(vivos, dict) or not vivos:
        return None
    sem_numero = float("inf")
    mac = min(vivos, key=lambda m: numeros.get(m, sem_numero))
    return mac, frozenset(vivos[mac].buttons_pressed)


def _anotar_a_mao(daemon: object, na_vaga: str | None) -> None:
    """O diário diz quando os atalhos mudam de mão — uma vez por episódio.

    Fora da vaga, o caminho de todo tique é um `getattr` e uma comparação.
    """
    antes = getattr(daemon, _MAO_DOS_ATALHOS, None)
    if not isinstance(antes, str):
        antes = None
    if antes == na_vaga:
        return
    try:
        setattr(daemon, _MAO_DOS_ATALHOS, na_vaga)
    except Exception as exc:  # dublê que recusa atributo: só o diário perde
        logger.debug("atalhos_mao_nao_anotada", err=str(exc))
    if na_vaga is None:
        logger.info("atalhos_voltam_ao_posto", de=antes)
    else:
        logger.info("atalhos_com_o_proximo_da_fila", uniq=na_vaga, de=antes)


class PollSubsystem:
    """Subsystem que encapsula o poll loop do daemon.

    Não executa o loop diretamente — ele é criado como asyncio.Task pelo Daemon
    e referenciado em daemon._tasks. A lógica de poll permanece em Daemon._poll_loop
    por compatibilidade com testes existentes que monkeypatching esse método.

    start() é chamado pelo Daemon.run() mas o loop real é iniciado via
    asyncio.create_task no Daemon. stop() é noop aqui (o loop para pelo stop_event).
    """

    name = "poll"

    async def start(self, ctx: object) -> None:
        """Noop: loop é criado como Task pelo Daemon."""
        logger.debug("poll_subsystem_start")

    async def stop(self) -> None:
        """Noop: loop para via stop_event do Daemon."""
        logger.debug("poll_subsystem_stop")

    def is_enabled(self, config: object) -> bool:
        return True


__all__ = [
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "BatteryDebouncer",
    "PollSubsystem",
    "botoes_dos_atalhos",
    "evdev_buttons_once",
    "observar_os_atalhos",
    "quem_segura_os_atalhos",
]
