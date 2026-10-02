"""Subsystem Rumble — re-asserção periódica de vibração com política de intensidade."""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

AUTO_DEBOUNCE_SEC = 5.0

#: ligado"*  (noqa-acento: citação literal dela).
TETO_DO_RUMBLE_FIXADO_S = 3.0

#:
#: **Por que o DESLIZADOR ainda vai até 200** (``RUMBLE_CUSTOM_MULT_MAX``, em
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


def escrever_rumble_no_dono(
    controller: Any, dono: str | None, weak: int, strong: int
) -> None:
    """Escreve o par no DONO dele; broadcast só quando dono nenhum foi fixado."""
    if isinstance(dono, str) and dono:
        mirar = getattr(controller, "set_rumble_for", None)
        if callable(mirar):
            if not mirar(dono, weak, strong):
                logger.debug("rumble_dono_fora_da_mesa", uniq=dono)
            return
    controller.set_rumble(weak=weak, strong=strong)


def _lembrar_dono_vibrando(cfg: Any, uniq: str | None) -> None:
    """Anota quem está vibrando por nossa conta — ou apaga a anotação."""
    try:
        cfg.rumble_dono_vibrando = uniq
    except Exception:  # pragma: no cover — config imutável/exótica
        logger.debug("rumble_dono_vibrando_nao_gravado", exc_info=True)


def silenciar_dono_abandonado(
    controller: Any, abandonado: str | None, dono_de_agora: str | None
) -> bool:
    """Zera o controle que vibrava quando o par TROCA de dono. Devolve se zerou.

    **MESA-CHEIA-05 (E0), terceira rodada — a rota de volta.** Congelar o dono
    matou a migração do par, mas criou o abandono: ela fixa 160/220 no Controle
    2, move o seletor para o 3 e clica «Parar» (ou aplica outro par). Os zeros
    vão para o 3, o dono passa a ser o 3, e o **Controle 2 fica em 220/160 sem
    receber mais escrita nenhuma**. Antes de haver dono, o reassert seguia o
    seletor e voltar o seletor ao 2 o silenciava; com o dono congelado, voltar o
    seletor deixou de significar coisa alguma. Medido nos dois mundos em 14/08,
    contra `git archive HEAD` — é a §5 da sprint: *"a volta ao neutro vale tanto
    quanto a ida"*.

    **O abandono não é só do «Parar», e por isso há DOIS chamadores.** As mesmas
    duas medições mostram `rumble.set` mirado no 3 deixando o 2 em 220/160 para
    sempre, e o «Aplicar» do rodapé faz o mesmo pela terceira porta. Então:

    * o `«Parar»` (`ipc_handlers._handle_rumble_stop`) chama AQUI na hora, sem
      esperar tick nenhum — parar é o gesto que quer dizer *cale o que está
      vibrando*, e quem vibra pode não ser o do seletor;
    * o `reassert_rumble` chama a cada tick do poll loop, comparando a anotação
      `config.rumble_dono_vibrando` com o dono de agora. É a rede que apanha
      TODAS as outras portas — inclusive as que nenhum chamador conhece.

    Três no-ops deliberados:

    * **sem abandonado** (`None`, ou config-dublê sem o campo) — não há a quem
      voltar;
    * **dono de agora é o mesmo** — o próprio par já reescreve nele;
    * **par de agora é broadcast** (`dono_de_agora is None`, alvo «Todos») — a
      escrita alcança o abandonado junto com todo mundo, e zerar antes só
      piscaria o motor dele.

    Com o abandonado fora da mesa, `escrever_rumble_no_dono` já é no-op por
    `set_rumble_for` devolvendo False: quem saiu levou os motores dele.
    """
    if not isinstance(abandonado, str) or not abandonado:
        return False
    if not isinstance(dono_de_agora, str) or not dono_de_agora:
        return False
    if abandonado == dono_de_agora:
        return False
    escrever_rumble_no_dono(controller, abandonado, 0, 0)
    logger.info(
        "rumble_dono_abandonado_silenciado", anterior=abandonado, agora=dono_de_agora
    )
    return True


def reassert_rumble(daemon: DaemonProtocol, now: float) -> None:
    """Re-aplica rumble_active no hardware a cada ~200ms com política."""
    from hefesto_dualsense4unix.core.rumble import _effective_mult

    cfg = daemon.config
    active = cfg.rumble_active
    if active is None:
        _lembrar_dono_vibrando(cfg, None)
        return
    # naquele momento isso nao interfere in game (noqa-acento: dela). (…) clicar
    # M2 (`lifecycle.apply_profile_rumble_passthrough`) preserva o silêncio
    carimbo = getattr(cfg, "rumble_active_em", None)
    if isinstance(carimbo, (int, float)) and now - carimbo > TETO_DO_RUMBLE_FIXADO_S:
        logger.info(
            "rumble_fixado_solto_por_ociosidade",
            parado_ha_s=round(now - carimbo, 1),
            teto_s=TETO_DO_RUMBLE_FIXADO_S,
            par=active,
            dono=getattr(cfg, "rumble_active_uniq", None),
        )
        cfg.rumble_active = None
        cfg.rumble_active_em = None
        _lembrar_dono_vibrando(cfg, None)
        return
    weak_raw, strong_raw = active

    battery_pct = 50
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

    dono = getattr(cfg, "rumble_active_uniq", None)
    try:
        silenciar_dono_abandonado(
            daemon.controller, getattr(cfg, "rumble_dono_vibrando", None), dono
        )
        escrever_rumble_no_dono(daemon.controller, dono, weak, strong)
    except Exception as exc:
        logger.warning("rumble_reassert_failed", err=str(exc), exc_info=True)
    _lembrar_dono_vibrando(cfg, dono if (weak or strong) else None)


def zero_motors_on_mode_exit(daemon: DaemonProtocol) -> None:
    """Zera os motores ao SAIR de um modo (HARM-16).

    Em passthrough (`rumble_active is None`) quem dirige os motores é o JOGO —
    pelo hidraw no Modo Nativo, pelo FF do vpad no modo gamepad. Ao sair do
    modo esse dono some no meio de uma vibração e NINGUÉM zera o hardware: o
    reassert do poll loop é no-op justamente em passthrough, então o controle
    fica vibrando para sempre (e o jogo perde a vibração).

    No-op com rumble FIXADO em par NÃO-NULO: ali o dono é a usuária (aba
    Rumble), o reassert re-afirmaria o valor em 200ms de qualquer forma e zerar
    seria desfazer o gesto dela. Best-effort: falha de hardware não pode
    abortar a troca de modo.

    **`(0, 0)` NÃO é par fixado para esta guarda** (25/08/2026). A guarda era
    `rumble_active is not None`, e `rumble.stop` — o botão "Parar" da aba —
    grava `(0, 0)`, que também não é `None`: **um clique em "Parar" desarmava
    a HARM-16 para o resto da sessão**. E o estado é vitalício por decisão
    medida: `lifecycle.apply_profile_rumble_passthrough` preserva o `(0, 0)`
    de propósito (nota M2), então nem a troca de perfil o solta — só
    "Devolver ao jogo" ou um rumble novo.

    Os dois motivos do no-op caem no `(0, 0)`, e é por isso que ele passa a
    zerar:

    - *"zerar seria desfazer o gesto dela"* — com `(0, 0)` zerar **é** o gesto
      dela, palavra por palavra;
    - *"o reassert re-afirmaria o valor de qualquer forma"* — não afirma: o
      reassert manda `set_rumble(0, 0)` e o dedup do `sendReport` come o
      report que não muda. É exatamente o buraco que `force_rumble_stop()`
      existe para tapar, e ele ficava sem chamador.

    É a mesma forma que a NATIVO-RUMBLE-01 já reconheceu numa porta e deixou
    aberta nesta (*"`(0,0)` não é `None`"*, `ipc_handlers._handle_rumble_stop`),
    e o mesmo teste de "vibrava por NOSSA conta" que `_handle_rumble_stop` e
    `_lembrar_dono_vibrando` já usam: `any(par)`.

    **O que foi medido e o que NÃO foi** (25/08/2026): medido que a guarda
    vira no-op após um `rumble.stop` e que os dois chamadores deixam de mandar
    o único report de parada que chega ao fio. **NÃO medido** que um motor
    fique girando por esse buraco: pelos escritores do próprio daemon ele não
    fica — `apply_game_rumble` ignora o FF do jogo com par fixado, e a entrada
    do Modo Nativo solta o par. Quem alcança o buraco é escritor de FORA
    (jogo no hidraw direto, Steam Input), que esta bancada não tem como medir.
    """
    par = daemon.config.rumble_active
    if par is not None and any(par):
        return
    try:
        force = getattr(daemon.controller, "force_rumble_stop", None)
        if callable(force):
            force()
        else:
            daemon.controller.set_rumble(weak=0, strong=0)
    except Exception as exc:
        logger.warning("rumble_zero_on_mode_exit_failed", err=str(exc), exc_info=True)


RUMBLE_APLICADO = "aplicado"
RUMBLE_PARADO = "parado"
RUMBLE_RECUSADO_MODO_NATIVO = "recusado_modo_nativo"
RUMBLE_SOLTO_NO_MODO_NATIVO = "solto_no_modo_nativo"
RUMBLE_RECUSADO_ALVO_AUSENTE = "recusado_alvo_ausente"

MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES = (
    "Vibração não aplicada: em Modo Nativo quem manda nos motores é o jogo. "
    "Saia do Modo Nativo para fixar a vibração por aqui."
)

MOTIVO_MODO_NATIVO_SOLTOU_O_PAR = (
    "Em Modo Nativo quem manda nos motores é o jogo, e o Hefesto não consegue "
    "pará-los. A vibração fixada por aqui foi solta — ela não volta quando o "
    "Modo Nativo sair."
)

#: nasceu no docstring de `PyDualSenseController.alvo_de_output_ausente`
MOTIVO_ALVO_FORA_DA_MESA = (
    "O controle escolhido não está na mesa — nada foi enviado."
)


def modo_nativo_manda_nos_motores(daemon: Any) -> bool:
    """O Modo Nativo está ligado — logo, o dono dos motores é o jogo."""
    if daemon is None:
        return False
    pergunta = getattr(daemon, "is_native_mode", None)
    if not callable(pergunta):
        return False
    try:
        return pergunta() is True
    except Exception as exc:
        logger.debug("modo_nativo_manda_nos_motores_falhou", err=str(exc))
        return False


class RumbleSubsystem:
    """Subsystem sentinela para o registry — lógica real está em reassert_rumble()."""

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
    "MOTIVO_ALVO_FORA_DA_MESA",
    "MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES",
    "MOTIVO_MODO_NATIVO_SOLTOU_O_PAR",
    "RUMBLE_APLICADO",
    "RUMBLE_PARADO",
    "RUMBLE_POLICY_MULT",
    "RUMBLE_RECUSADO_ALVO_AUSENTE",
    "RUMBLE_RECUSADO_MODO_NATIVO",
    "RUMBLE_SOLTO_NO_MODO_NATIVO",
    "RumbleSubsystem",
    "escrever_rumble_no_dono",
    "modo_nativo_manda_nos_motores",
    "reassert_rumble",
    "sem_dono_do_rumble",
    "silenciar_dono_abandonado",
    "zero_motors_on_mode_exit",
]
