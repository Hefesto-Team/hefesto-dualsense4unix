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


def escrever_rumble_no_dono(
    controller: Any, dono: str | None, weak: int, strong: int
) -> None:
    """Escreve o par no DONO dele; broadcast só quando dono nenhum foi fixado.

    MESA-CHEIA-05 (E0), e é o único lugar que sabe desviar do seletor global:
    quem tem `dono` (um MAC) escreve por `set_rumble_for` — a rota por MAC que
    já existia e não toca o ponteiro `_output_target_key`. Quem não tem cai no
    `set_rumble` de sempre.

    **Dono ausente da mesa é NO-OP, não broadcast.** `set_rumble_for` devolve
    False quando o MAC não casa com handle nenhum; cair no broadcast ali
    levaria o valor de um controle que saiu para todos os que ficaram — o
    mesmo defeito de migração, pela outra porta.

    Backend sem `set_rumble_for` (dublês, single-instance) cai no caminho
    histórico — a mesma tolerância por `getattr` que o force-feedback do jogo
    já usa (`subsystems/gamepad.py`).
    """
    # `isinstance(str)`: só um MAC endereça alguém. Dublê de config que devolve
    # um objeto qualquer para qualquer atributo não vira alvo por acidente.
    if isinstance(dono, str) and dono:
        mirar = getattr(controller, "set_rumble_for", None)
        if callable(mirar):
            if not mirar(dono, weak, strong):
                logger.debug("rumble_dono_fora_da_mesa", uniq=dono)
            return
    controller.set_rumble(weak=weak, strong=strong)


def _lembrar_dono_vibrando(cfg: Any, uniq: str | None) -> None:
    """Anota quem está vibrando por nossa conta — ou apaga a anotação.

    Tolerante de propósito: configs-dublê (`SimpleNamespace`, `MagicMock`) e
    daemons antigos vivos em `install --editable` não têm o campo, e uma anotação
    que não pode ser gravada só custa o resgate — nunca o tick.
    """
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
    """Re-aplica rumble_active no hardware a cada ~200ms com política.

    Idempotente. Necessário porque writes HID de LED/trigger podem zerar os
    motores de vibração involuntariamente. A re-asserção a 5Hz (200ms) garante
    que o valor fixado pelo usuário persista mesmo com outras escritas HID.

    Pula silenciosamente se:
    - rumble_active is None (passthrough — jogo/UDP controla).
    - Controle não está conectado.

    **MESA-CHEIA-05 (E0) — o par fixado NÃO migra de dono.** Enquanto isto
    chamava `set_rumble` seco, o destino era o `_output_target_key` do backend
    — um ponteiro mutável: ela fixava 160/220 no Controle 2, trocava o seletor
    para o 3 por outro motivo, e 200 ms depois o 3 recebia o valor do 2. Agora
    o par carrega o dono (`config.rumble_active_uniq`, congelado no gesto que
    fixou) e o reassert reescreve NAQUELE controle, pela rota por MAC que já
    existia (`set_rumble_for`) e só o co-op e o force-feedback usavam.

    Com o dono fora da mesa, `set_rumble_for` devolve False e o tick é no-op —
    de propósito: cair no broadcast levaria o valor de um controle ausente
    para todos os presentes, que é o defeito de volta pela outra porta. Quando
    ele voltar, o próximo tick o reencontra.

    Sem dono (`rumble_active_uniq is None` — o alvo era "Todos", ou o backend
    não sabe endereçar) segue o caminho histórico: `set_rumble`, que é
    broadcast quando não há alvo.

    **E o dono TROCA sem ninguém avisar o abandonado** (terceira rodada, 14/08):
    por isso cada tick passa por `silenciar_dono_abandonado` antes de escrever —
    ver a prosa dele. Em passthrough a anotação é APAGADA em vez de resgatada:
    ali quem dirige os motores é o jogo, e um zero nosso atravessaria a vibração
    dele. Isso mantém a saída do passthrough idêntica ao que sempre foi.
    """
    # Import local: core/rumble.py -> daemon/lifecycle.py (TYPE_CHECKING) ->
    # daemon/subsystems/rumble.py. Import no topo criaria ciclo em runtime.
    from hefesto_dualsense4unix.core.rumble import _effective_mult

    cfg = daemon.config
    active = cfg.rumble_active
    if active is None:
        _lembrar_dono_vibrando(cfg, None)
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

    dono = getattr(cfg, "rumble_active_uniq", None)
    try:
        silenciar_dono_abandonado(
            daemon.controller, getattr(cfg, "rumble_dono_vibrando", None), dono
        )
        escrever_rumble_no_dono(daemon.controller, dono, weak, strong)
    except Exception as exc:
        logger.warning("rumble_reassert_failed", err=str(exc), exc_info=True)
    # Só quem recebeu um par NÃO-NULO fica na anotação: zero não abandona
    # ninguém, e um endereço rançoso aqui custaria uma escrita a mais no
    # próximo dono.
    _lembrar_dono_vibrando(cfg, dono if (weak or strong) else None)


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


# --- NATIVO-RUMBLE-01: o Modo Nativo RECUSA fixar vibração ------------------
#
# **O defeito, medido em 19/08/2026.** No Modo Nativo o backend muta TODA
# escrita de output (`lifecycle._release_controller_to_game` →
# `backend_pydualsense.set_output_mute(True)`), e o mute é a ÚNICA porta antes
# do `sendReport`. Medido: `rumble.set` dentro do modo produz **zero write no
# fio** e mesmo assim o daemon respondia `{"status": "ok"}` — a aba dizia
# "Vibração travada (fraca=…, forte=…)" com o motor parado.
#
# **E a parte destrutiva não é a tela que mente, é o estado que sobrevive ao
# modo.** Gravar `daemon.config.rumble_active` DESARMA a cura HARM-16: o
# `zero_motors_on_mode_exit` logo acima só zera os motores em passthrough
# (`rumble_active is None`), justamente porque com par fixado o dono é a
# usuária. Com um par gravado durante o modo, a saída do Modo Nativo deixa de
# zerar o hardware — e quem estava vibrando ali era o JOGO, escrevendo direto
# no hidraw. Resultado: o controle sai do modo vibrando, e ninguém mais zera.
#
# **A decisão dela (19/08/2026), com as três opções na mesa** — recusar no
# daemon, impedir o clique na tela, ou as duas: *"a aba Gatilhos já sabe exibir
# recusa vinda do daemon"*. O mecanismo existe e só precisava ser usado aqui.
# Impedir o clique foi descartado porque contraria a regra da casa de que **a
# vontade da GUI prevalece**: recusar com motivo diz o que aconteceu, impedir
# esconde a escolha.
#
# **Por que "recusado" e não "guardado".** As outras abas usam
# `app.textos_de_aplicacao.guardado_ate_o_nativo_sair` — o desejado fica
# registrado e é re-escrito no desmute. Para o rumble essa palavra seria a
# própria bomba: guardar o par É o que desarma a HARM-16. Aqui o pedido não
# fica pendurado; ele é recusado, e a frase diz o que fazer.

#: O vocabulário de desfecho do rumble fixado — o mesmo contrato que a leva
#: VERDADE-01 (18-19/08) criou para o gamepad em `subsystems.gamepad`, pela
#: mesma razão: um `bool` que valia para "aplicou", "já estava" e "bloqueado"
#: foi a mentira que fez um laço destruir e recriar o vpad no meio da partida.
#: Quem só quer saber se pode confiar no par lê o `status`; quem precisa da
#: verdade inteira lê o `desfecho`.
#:
#:   - ``"aplicado"``              — o par foi fixado e o reassert vai re-afirmá-lo;
#:   - ``"parado"``                — o pedido era calar, e o silêncio foi fixado;
#:   - ``"recusado_modo_nativo"``  — o Modo Nativo está ligado: NADA foi armado,
#:                                   nem no `rumble_active` nem no hardware;
#:   - ``"solto_no_modo_nativo"``  — o pedido era calar DENTRO do modo. O Hefesto
#:                                   não consegue calar o jogo, mas soltou o par
#:                                   que estivesse fixado (volta ao passthrough).
RUMBLE_APLICADO = "aplicado"
RUMBLE_PARADO = "parado"
RUMBLE_RECUSADO_MODO_NATIVO = "recusado_modo_nativo"
RUMBLE_SOLTO_NO_MODO_NATIVO = "solto_no_modo_nativo"

#: A frase é para uma PESSOA: o que aconteceu, e o que fazer a respeito. O
#: léxico é o que já está na tela — "Modo Nativo" e "quem manda ... é o jogo"
#: são as mesmas palavras de `app.textos_de_aplicacao._MOTIVO_NATIVO`, com
#: "no controle" trocado por "nos motores" porque é dos motores que se fala.
MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES = (
    "Vibração não aplicada: em Modo Nativo quem manda nos motores é o jogo. "
    "Saia do Modo Nativo para fixar a vibração por aqui."
)

#: O "Parar" tem frase PRÓPRIA porque o desfecho é outro, e dizer a frase de
#: cima seria mentir por omissão: o gesto fez alguma coisa (soltou o par), só
#: não fez a que ela esperava (calar o motor que o jogo está tocando).
MOTIVO_MODO_NATIVO_SOLTOU_O_PAR = (
    "Em Modo Nativo quem manda nos motores é o jogo, e o Hefesto não consegue "
    "pará-los. A vibração fixada por aqui foi solta — ela não volta quando o "
    "Modo Nativo sair."
)


def modo_nativo_manda_nos_motores(daemon: Any) -> bool:
    """O Modo Nativo está ligado — logo, o dono dos motores é o jogo.

    Um lugar só para a pergunta, pelo mesmo motivo que
    `app.textos_de_aplicacao.modo_nativo_manda_no_output` é um lugar só para a
    frase: as três portas que armam `rumble_active` (o `rumble.set` da aba, o
    `rumble.stop` e o "Aplicar" do rodapé, em `ipc_draft_applier`) têm de
    responder a MESMA coisa. Duas cópias divergem, e a que divergir vira o
    vazamento silencioso.

    `getattr` defensivo e `False` como padrão: sem daemon (testes de handler
    isolado) ou sem o método, não há Modo Nativo para recusar — não se inventa
    uma recusa por não saber.

    **A resposta tem de ser `True` DE VERDADE, e não só verdadeira** — a
    diferença é medida, não teórica: com `bool(...)` no lugar do `is True`,
    catorze testes da MESA-CHEIA-05 e sete da ONDA-U passaram a reprovar de uma
    vez, porque montam a mesa com `daemon = MagicMock()` e todo `MagicMock()`
    responde verdadeiro a qualquer pergunta. O contrato de `DaemonProtocol.
    is_native_mode` é `-> bool`, então quem responde outra coisa é um dublê — e
    um dublê não decide o destino da vibração dela. É a mesma regra do resto da
    casa: não afirmar o que não se sabe.
    """
    if daemon is None:
        return False
    pergunta = getattr(daemon, "is_native_mode", None)
    if not callable(pergunta):
        return False
    try:
        return pergunta() is True
    except Exception as exc:  # observabilidade > silêncio
        logger.debug("modo_nativo_manda_nos_motores_falhou", err=str(exc))
        return False


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
    "MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES",
    "MOTIVO_MODO_NATIVO_SOLTOU_O_PAR",
    "RUMBLE_APLICADO",
    "RUMBLE_PARADO",
    "RUMBLE_POLICY_MULT",
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
