"""Subsystem Rumble — re-asserção periódica de vibração com política de intensidade.

Responsabilidades:
  - Re-aplicar rumble_active no hardware a cada ~200ms.
  - Delegar cálculo de multiplicador para `hefesto_dualsense4unix.core.rumble._effective_mult`
    (fonte canônica única — AUDIT-FINDING-RUMBLE-POLICY-DEDUP-01).
  - Zerar os motores quando um modo termina e o dono da vibração some
    (`zero_motors_on_mode_exit` — HARM-16).

O estado de debounce da política "auto" (_last_auto_mult, _last_auto_change_at)
é mantido diretamente no objeto Daemon por compatibilidade com testes existentes.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

# FEAT-RUMBLE-POLICY-01
AUTO_DEBOUNCE_SEC = 5.0

#: A escada da intensidade, e o dono único dos três números.
#:
#: DECISÃO DELA — 11/08/2026, depois de o preço de cada opção ir para a mesa.
#: A escada da tela passa a ser **30% / 100% / 150%**.
#:
#: * ``balanceado`` era **0,7**, e o tooltip da tela sempre prometeu *"do jeito
#:   que o jogo pediu, sem aumentar nem diminuir"*. Eram duas afirmações e uma
#:   mentira; quem sai é o número. Em **1,0** o botão entrega o que promete.
#: * ``max`` era **1,0** — exatamente o mesmo que não mexer em nada. Um botão
#:   chamado "Máximo" que não aumentava coisa alguma não tinha razão de existir.
#:   Em **1,5** ele AMPLIFICA, acima do que o jogo pediu.
#:
#: **A amplificação está MEDIDA no aparelho** (11/08/2026): um report com
#: ``common[2]=200``, com o daemon parado, fez o motor obedecer, e ela conferiu
#: de olho. Os bytes de motor são 0-255 e o firmware honra o valor.
#:
#: **Quem multiplica satura em 255**, e isso não é detalhe: um valor acima de
#: 255 truncado em byte viraria lixo (256 → 0, o motor PARARIA no pico). A
#: conta é ``max(0, min(255, round(bruto * mult)))`` e ela vive em três lugares,
#: todos com o mesmo recorte — ``reassert_rumble`` logo abaixo (rumble fixado),
#: ``daemon.ipc_rumble_policy.apply_rumble_policy`` (o ``rumble.set`` da aba e o
#: "Aplicar" do rodapé) e ``daemon.subsystems.gamepad.apply_game_rumble`` (o
#: rumble do JOGO). ``core.rumble._clamp`` faz o mesmo no ``RumbleEngine``.
#:
#: **O 2,0 FOI CONSIDERADO E DESCARTADO POR ELA**, no mesmo 11/08, e o motivo é
#: a medição da nota SATURA-01 — que não caducou: ela VENCEU EM PARTE. Rodando
#: a conta exata acima sobre os 256 valores que o jogo pode pedir:
#:
#:     mult 1,0 → nenhum valor satura
#:     mult 1,5 → satura a partir de 170: 33% da faixa vira 255
#:     mult 2,0 → satura a partir de 128: METADE da faixa vira 255
#:
#: A 2,0 o jogo manda 128, 180 e 255 e o controle recebe 255 nas três: naquela
#: metade a variação da vibração some, e o que se sente é força CONSTANTE, não
#: força maior. Foi o que ela relatou em 10/08 — *"vibra muito mais do que o
#: normal a ponto de não parar"*. Amplificar sem nuance não é amplificar: é
#: achatar.
#:
#: **O que o 1,5 compra:** amplificação de verdade com dois terços da faixa
#: ainda variando (satura só a partir de 170). É o ponto em que o botão faz o
#: que o nome dele diz sem achatar a metade forte das cenas — o preço aceito é
#: um terço, não a metade.
#:
#: **Por que o DESLIZADOR ainda vai até 200** (``RUMBLE_CUSTOM_MULT_MAX``, em
#: ``profiles.schema``) — e isto NÃO é incoerência, é a divisão de papéis:
#: os quatro botões são **presets seguros**, escolhidos por ela para quem só
#: quer clicar; o deslizador é o **ajuste livre** de quem quer ir além e aceita
#: o preço, que agora está escrito no tooltip. Um preset que achata metade da
#: faixa é armadilha; um número que a pessoa arrasta até 200 de propósito é
#: escolha dela.
#:
#: O caminho para amplificar SEM achatar continua sendo comprimir (uma curva)
#: em vez de cortar, e continua por fazer.
RUMBLE_POLICY_MULT: dict[str, float] = {
    "economia": 0.3,
    "balanceado": 1.0,
    "max": 1.5,
}


def sem_dono_do_rumble(*, native: bool, backends: Sequence[str]) -> bool:
    """RUMBLE-SEM-DONO-01: o quadrante em que a vibração não passa por nós.

    MEDIDO na máquina dela em 11/08/2026 — o journal do daemon registrava
    `launch_env_materializado ... backends=[] emulacao=False ... native=False`,
    e é esse par que define o buraco:

    - **sem gamepad virtual** (`backends` vazio) o multiplicador de intensidade
      da GUI não age, porque ele mora no `rumble_sink` do vpad
      (`subsystems/gamepad.make_primary_rumble_sink` → `apply_game_rumble`).
      Sem vpad, o sink não existe e o EV_FF do jogo vai direto ao nó físico:
      o slider dela deixa de valer sem avisar;
    - **sem Modo Nativo** o output do daemon não é mutado
      (`lifecycle._release_controller_to_game`), então continuamos escrevendo
      no mesmo controle que o jogo está dirigindo.

    Nos outros três quadrantes uma das duas coisas protege — por isso o defeito
    parecia intermitente.

    **DOIS CHAMADORES, UM CRITÉRIO SÓ** (11/08/2026). Quando esta função nasceu,
    o produto não contava o quadrante em tela nenhuma e o journal era o mínimo
    honesto; a decisão de mostrá-lo era dela, e ela a tomou no mesmo dia. Hoje:

    - ``daemon.launch_env.materialize_launch_env`` emite ``rumble_sem_dono`` no
      journal — a borda com o estado REAL da mesa;
    - ``app.actions.rumble_actions.texto_do_alcance_da_intensidade`` acende o
      aviso na aba Rumble, em cima dos quatro botões de intensidade.

    Os dois passam por AQUI de propósito. Chegaram a ter critérios paralelos por
    algumas horas (a borda olhava ``backends``, a tela olhava
    ``rumble_ff.vpads`` do ``state_full``), e dois critérios para o mesmo
    quadrante divergem na primeira mudança — a classe de defeito que o HARM-19
    já pagou no teto do multiplicador. A tela traduz a contagem de gamepads
    virtuais numa sequência antes de perguntar; o predicado só olha a
    verdade/falsidade de ``backends`` ("há gamepad virtual?"), então contagem e
    lista respondem a mesma pergunta.

    **O que a tela diz A MAIS, e não cabe aqui:** no Modo Nativo a intensidade
    também não alcança a vibração do jogo, mas isso é o modo funcionando como
    deve — não é defeito, e por isso não é este quadrante. A frase de lá é
    outra, e não manda ninguém consertar nada.
    """
    return not native and not backends


def reassert_rumble(daemon: DaemonProtocol, now: float) -> None:
    """Re-aplica rumble_active no hardware a cada ~200ms com política.

    Idempotente. Necessário porque writes HID de LED/trigger podem zerar os
    motores de vibração involuntariamente. A re-asserção a 5Hz (200ms) garante
    que o valor fixado pelo usuário persista mesmo com outras escritas HID.

    Pula silenciosamente se:
    - rumble_active is None (passthrough — jogo/UDP controla).
    - Controle não está conectado.
    """
    # Import local: core/rumble.py -> daemon/lifecycle.py (TYPE_CHECKING) ->
    # daemon/subsystems/rumble.py. Import no topo criaria ciclo em runtime.
    from hefesto_dualsense4unix.core.rumble import _effective_mult

    cfg = daemon.config
    active = cfg.rumble_active
    if active is None:
        return
    weak_raw, strong_raw = active

    battery_pct = 50  # fallback neutro
    try:
        snap = daemon.store.snapshot()
        ctrl = snap.controller
        if ctrl is not None and ctrl.battery_pct is not None:
            battery_pct = int(ctrl.battery_pct)
    except Exception:
        logger.debug("rumble_state_read_fallback", exc_info=True)

    mult, daemon._last_auto_mult, daemon._last_auto_change_at = _effective_mult(
        config=cfg,
        battery_pct=battery_pct,
        now=now,
        last_auto_mult=daemon._last_auto_mult,
        last_auto_change_at=daemon._last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )
    weak = max(0, min(255, round(weak_raw * mult)))
    strong = max(0, min(255, round(strong_raw * mult)))

    try:
        daemon.controller.set_rumble(weak=weak, strong=strong)
    except Exception as exc:
        logger.warning("rumble_reassert_failed", err=str(exc), exc_info=True)


def zero_motors_on_mode_exit(daemon: DaemonProtocol) -> None:
    """Zera os motores ao SAIR de um modo (HARM-16).

    Em passthrough (`rumble_active is None`) quem dirige os motores é o JOGO —
    pelo hidraw no Modo Nativo, pelo FF do vpad no modo gamepad. Ao sair do
    modo esse dono some no meio de uma vibração e NINGUÉM zera o hardware: o
    reassert do poll loop é no-op justamente em passthrough, então o controle
    fica vibrando para sempre (e o jogo perde a vibração).

    No-op com rumble FIXADO (`rumble_active` não-None): ali o dono é a usuária
    (aba Rumble), o reassert re-afirmaria o valor em 200ms de qualquer forma e
    zerar seria desfazer o gesto dela. Best-effort: falha de hardware não pode
    abortar a troca de modo.
    """
    if daemon.config.rumble_active is not None:
        return
    try:
        # RUMBLE-SEM-DONO-01: `set_rumble(0, 0)` com os motores do backend JÁ
        # em 0 não MUDA o report, e report que não muda não vai ao fio (dedup
        # do `sendReport`) — logo nada para o motor que o jogo deixou girando
        # por fora (hidraw direto). O backend pydualsense
        # expõe `force_rumble_stop()` (um report de stop de verdade); os
        # demais backends/fakes seguem no zero clássico.
        force = getattr(daemon.controller, "force_rumble_stop", None)
        if callable(force):
            force()
        else:
            daemon.controller.set_rumble(weak=0, strong=0)
    except Exception as exc:
        logger.warning("rumble_zero_on_mode_exit_failed", err=str(exc), exc_info=True)


class RumbleSubsystem:
    """Subsystem sentinela para o registry — lógica real está em reassert_rumble().

    A re-asserção periódica de rumble é integrada diretamente no poll loop
    do Daemon por requisitos de timing (a cada 200ms dentro do tick). Este
    subsystem existe para completar o registry e servir como ponto de extensão
    para futuras políticas de rumble desacopladas do poll loop.
    """

    name = "rumble"

    async def start(self, ctx: DaemonContext) -> None:
        """Noop: re-asserção é integrada ao poll loop."""
        logger.debug("rumble_subsystem_start")

    async def stop(self) -> None:
        """Noop: não há recurso externo para liberar."""
        logger.debug("rumble_subsystem_stop")

    def is_enabled(self, config: Any) -> bool:
        return True


__all__ = [
    "AUTO_DEBOUNCE_SEC",
    "RUMBLE_POLICY_MULT",
    "RumbleSubsystem",
    "reassert_rumble",
    "sem_dono_do_rumble",
    "zero_motors_on_mode_exit",
]
