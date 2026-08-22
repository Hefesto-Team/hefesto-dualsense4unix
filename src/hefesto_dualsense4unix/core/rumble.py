"""Motor de rumble com throttle anti-spam e política de intensidade.

Rumble passado do jogo (via UDP ou passthrough) pode chegar a centenas de
Hz. Aplicar cada atualização esgota a bateria, satura o motor HID e
deteriora os motors pequenos do DualSense. `RumbleEngine` agrupa os
comandos recebidos numa janela curta e aplica só o último a cada tick
de saída.

FEAT-RUMBLE-POLICY-01: política de intensidade global (economia/balanceado/
max/auto/custom) aplica multiplicador sobre weak e strong antes de enviar ao
hardware. O multiplicador do modo "auto" usa a bateria do estado mais recente
com debounce de 5s para evitar oscilação em limiar de threshold.

Uso:
    engine = RumbleEngine(controller, min_interval_sec=0.02)
    engine.set(weak=80, strong=150)    # pode ser chamado 1000x/s
    # tick() é chamado pelo poll loop do daemon e aplica se janela
    # estourou. Também aplica automaticamente quando weak+strong cai
    # para 0 (garantir desligamento imediato).
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

DEFAULT_MIN_INTERVAL_SEC = 0.02  # 50Hz ceiling para motores HID
RUMBLE_MIN = 0
RUMBLE_MAX = 255


@dataclass
class RumbleCommand:
    weak: int
    strong: int

    def is_stop(self) -> bool:
        return self.weak == 0 and self.strong == 0


#: CONFIG-05 (22/08/2026): a única chave de orçamento da mesa que IMPÕE teto
#: hoje. As outras três não impõem nenhum, e por dois motivos diferentes:
#: ``balanceado`` e ``max`` porque a dica delas promete, palavra por palavra,
#: *"tudo como o jogo pedir, sem teto"*; ``auto`` porque o teto dele seria
#: MÓVEL — muda a cada tique com a bateria —, e a casa já decidiu não prometer
#: número móvel na tela (`profiles/manager.py:1556-1567`, o pulo com log
#: `escala_de_vibracao_pulada_base_movel`).
_ORCAMENTO_COM_TETO = "economia"


def teto_do_orcamento(orcamento: str | None) -> float | None:
    """O teto que o orçamento da mesa impõe ao multiplicador, ou ``None``.

    ``None`` quer dizer **não há teto**, e a tela precisa distinguir isso de um
    teto de 100 %: sem teto, o que o jogo pedir chega inteiro, inclusive o
    150 % do "Máximo". Devolvem ``None`` o orçamento não declarado (ninguém
    escolheu), o ``balanceado``, o ``max`` e o ``auto`` — os motivos estão em
    ``_ORCAMENTO_COM_TETO``, logo acima.

    **O 0,3 não se escreve aqui.** Ele é o mesmo degrau que a política de
    vibração "Economia" já entrega (``RUMBLE_POLICY_MULT["economia"]``), e é
    isso que faz a frase da tela ser verificável: o orçamento em Economia
    entrega exatamente a força que o botão Economia entrega. Dois números
    divergiriam na primeira mudança de degrau — é o HARM-19 pela outra porta.

    Import tardio da tabela pela mesma razão do corpo de ``_effective_mult``:
    ``core`` não importa ``daemon`` no topo, senão fecha o ciclo com
    ``daemon.subsystems.rumble``, que importa este módulo.
    """
    if orcamento != _ORCAMENTO_COM_TETO:
        return None
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    return RUMBLE_POLICY_MULT[_ORCAMENTO_COM_TETO]


def _sob_o_teto(mult: float, teto: float | None) -> float:
    """``mult`` limitado por ``teto`` — ``min``, **nunca** produto.

    Teto que multiplica não é teto: 0,3 sobre um ``custom`` já amplificado a
    2,0 entrega 0,6, ou seja, o dobro do que o Economia prometeu, e mais forte
    que o próprio Balanceado. Com ``min`` o pedido de 2,0 chega em 0,3, que é o
    número escrito na tela.

    E ``min`` preserva o denominador de ``_controllers_to_rumble_scales``
    (`profiles/manager.py:1541-1546`): o valor que chega ao backend já vem
    escalado pela política global, então o fator por unidade é RELATIVO — um
    produto mexeria na base daquela conta sem ninguém saber.
    """
    if teto is None:
        return mult
    return min(mult, teto)


def _orcamento_declarado(config: Any) -> str | None:
    """A chave do orçamento da mesa que vale AGORA, ou ``None``.

    A config não carrega uma CÓPIA da escolha: carrega a fonte dela
    (``DaemonConfig.orcamento_da_mesa``, fiada no boot em
    ``daemon/lifecycle.py``). A diferença é o gesto do "Aplicar": o
    ``machine.declare`` relê o ``maquina.json`` e REBINDA ``daemon._maquina``,
    então uma cópia feita no boot ficaria velha exatamente no instante em que
    ela acabou de escolher — e o teto novo só valeria no próximo início do
    Hefesto.

    Tolerante de propósito: config sem o campo (dublê de teste, daemon de uma
    versão anterior no meio de um upgrade) e fonte que levante devolvem
    ``None``, que é "nenhum teto" — nunca um teto inventado.
    """
    fonte = getattr(config, "orcamento_da_mesa", None)
    if fonte is None:
        return None
    valor: Any = None
    with contextlib.suppress(Exception):
        valor = fonte()
    return valor if isinstance(valor, str) else None


def _effective_mult(
    config: DaemonConfig,
    battery_pct: int,
    now: float,
    last_auto_mult: float,
    last_auto_change_at: float,
    auto_debounce_sec: float = 5.0,
) -> tuple[float, float, float]:
    """Calcula multiplicador efetivo conforme política do config.

    Retorna (mult, novo_last_auto_mult, novo_last_auto_change_at).
    Os dois últimos valores devem ser guardados no estado do chamador
    para o debounce do modo "auto" funcionar corretamente entre chamadas.

    `novo_last_auto_mult` é SEMPRE o último mult efetivo: além de âncora do
    debounce do "auto", ele é a fonte da observabilidade (o poll loop o
    guarda em `daemon._last_auto_mult`, que o `daemon.state_full` expõe como
    `rumble_mult_applied`). MISC-08 item 1 (2026-07-18): as políticas fixas
    devolviam `last_auto_mult` INTOCADO, então o campo ficava preso no
    default 0.7 — ao vivo, policy=max reportava `rumble_mult_applied=0.7` e
    parecia atenuação real do rumble do jogo (o hardware recebia 1.0).

    Modo "auto" — a escada dele é PRÓPRIA, e nunca amplifica:
      - bateria >50% -> mult 1.0 (o que o jogo pediu, sem aumentar)
      - bateria 20-50% -> mult 0.7
      - bateria <20% -> mult 0.3
      Com debounce de `auto_debounce_sec` para evitar oscilação.

    **Por que o teto do auto é 1.0 e não o do "Máximo"** (11/08/2026): o auto
    existe para POUPAR bateria — amplificar seria fazer o oposto do que ele
    promete, e ainda por cima sozinho, sem ela ter pedido. Os três degraus
    acima não são os de `RUMBLE_POLICY_MULT`: desde que "Máximo" subiu acima do
    "Balanceado", o degrau de cima do auto empatou com o balanceado, e é isso
    mesmo. Quem mexer nesta escada mexe no texto que a promete na tela: o
    `rumble_policy_auto_label` do `gui/main.glade`, que é o dono único da frase
    desde 11/08/2026 (havia uma cópia morta em `app.actions.rumble_actions`,
    nunca usada por ninguém e já desatualizada).

    **O TETO DO ORÇAMENTO DA MESA ENTRA AQUI, E SÓ AQUI** (CONFIG-05,
    22/08/2026). Este é o funil dos TRÊS caminhos de vibração do produto —
    ``ipc_rumble_policy.apply_rumble_policy`` (o ``rumble.set`` e o "Aplicar" do
    rodapé), ``subsystems.gamepad._game_rumble_mult`` (o force-feedback do
    JOGO) e ``subsystems.rumble.reassert_rumble`` (o tique de 200 ms do rumble
    fixado) —, então um ponto de aplicação basta e não há como um caminho
    escapar do teto. As QUATRO saídas o respeitam, o fallback de política
    desconhecida inclusive: deixar uma de fora abriria um caminho em que o
    orçamento simplesmente não vale.

    **Teto, não troca**: o ``config.rumble_policy`` dela não é reescrito em
    lugar nenhum. Voltar o orçamento para Balanceado devolve o mult inteiro sem
    ela reclicar coisa alguma — é essa a invariante, e ela tem teste
    (``tests/unit/test_orcamento_e_teto_nao_troca.py``).
    """
    from hefesto_dualsense4unix.daemon.lifecycle import RUMBLE_POLICY_MULT

    policy = config.rumble_policy
    teto = teto_do_orcamento(_orcamento_declarado(config))

    if policy == "custom":
        mult = _sob_o_teto(float(config.rumble_policy_custom_mult), teto)
        return mult, mult, last_auto_change_at

    if policy in RUMBLE_POLICY_MULT:
        mult = _sob_o_teto(RUMBLE_POLICY_MULT[policy], teto)
        return mult, mult, last_auto_change_at

    if policy == "auto":
        # Calcula mult alvo baseado em bateria.
        if battery_pct > 50:
            target = 1.0
        elif battery_pct >= 20:
            target = 0.7
        else:
            target = 0.3

        # O teto entra ANTES do debounce, e a ordem é a cura. Limitar só o
        # valor devolvido deixaria a âncora do debounce (`last_auto_mult`) com
        # o degrau CRU: a cada chamada `target != last_auto_mult` seria
        # verdadeiro, o "auto" se declararia em mudança para sempre e o journal
        # ganharia um `rumble_auto_policy_change` por tique. Limitando o alvo,
        # a escada do auto sob um orçamento Economia é 0,3 constante — que é o
        # que a tela promete —, e o debounce assenta na primeira volta.
        target = _sob_o_teto(target, teto)

        # Debounce: só muda se transcorreu tempo suficiente desde a última mudança.
        if target != last_auto_mult:
            elapsed = now - last_auto_change_at
            if elapsed >= auto_debounce_sec or last_auto_change_at == 0.0:
                if target != last_auto_mult:
                    logger.info(
                        "rumble_auto_policy_change",
                        mult=target,
                        battery_pct=battery_pct,
                    )
                return target, target, now
            # Dentro do debounce: manter mult anterior.
            return last_auto_mult, last_auto_mult, last_auto_change_at

        return last_auto_mult, last_auto_mult, last_auto_change_at

    # Política desconhecida: fallback para balanceado (estado observável
    # acompanha — mesma regra das políticas fixas acima).
    #
    # 11/08/2026: era o literal `0.7`, que ERA o balanceado. Quando o
    # balanceado virou 1.0 este número ficou sendo um degrau que não existe
    # mais em lugar nenhum — âncora morta. Derivar da tabela mantém a promessa
    # do comentário ("fallback para balanceado") verdadeira sozinha.
    fallback = _sob_o_teto(RUMBLE_POLICY_MULT["balanceado"], teto)
    logger.warning("rumble_policy_desconhecida", policy=policy)
    return fallback, fallback, last_auto_change_at


class RumbleEngine:
    """Throttle com política de intensidade (FEAT-RUMBLE-POLICY-01).

    Guarda o último comando pedido; `tick(now)` aplica se o intervalo
    estourou OU se o comando é stop (0,0). Em stop o throttle é ignorado
    para garantir desligamento imediato quando o jogo solta o gatilho.

    A política de rumble é aplicada pelo método `_apply_with_policy` antes
    de enviar ao hardware. Requer `link(config, state_ref)` para funcionar
    em modo não-default.
    """

    def __init__(
        self,
        controller: IController,
        min_interval_sec: float = DEFAULT_MIN_INTERVAL_SEC,
        *,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._controller = controller
        self._min_interval = min_interval_sec
        self._time = time_fn or time.monotonic
        self._pending: RumbleCommand | None = None
        self._last_applied: RumbleCommand | None = None
        self._last_applied_at: float = 0.0
        # Referências injetadas via link() para aplicar política.
        self._config: Any | None = None
        self._state_ref: Any | None = None
        # Debounce do modo "auto".
        self._last_auto_mult: float = 0.7
        self._last_auto_change_at: float = 0.0
        # Último mult efetivo para exposição via IPC (daemon.state_full).
        self._last_mult_applied: float = 1.0

    def link(self, config: DaemonConfig, state_ref: Any) -> None:
        """Injeta referência ao DaemonConfig e ao estado do controle.

        `state_ref` deve ter atributo `battery_pct: int`; pode ser o objeto
        ControllerState mais recente guardado pelo poll loop, ou qualquer
        objeto com duck-typing compatível.
        """
        self._config = config
        self._state_ref = state_ref

    def set(self, weak: int, strong: int) -> None:
        weak = _clamp(weak)
        strong = _clamp(strong)
        self._pending = RumbleCommand(weak=weak, strong=strong)

    def tick(self) -> RumbleCommand | None:
        """Aplica `pending` se tempo permitir. Retorna o comando aplicado ou None."""
        if self._pending is None:
            return None

        now = self._time()
        cmd = self._pending

        if cmd.is_stop():
            return self._apply(cmd, now)

        if self._last_applied is None:
            return self._apply(cmd, now)

        interval = now - self._last_applied_at
        if interval >= self._min_interval:
            return self._apply(cmd, now)
        return None

    def stop(self) -> None:
        """Forçar desligamento imediato dos motores."""
        self.set(0, 0)
        self.tick()

    @property
    def last_applied(self) -> RumbleCommand | None:
        return self._last_applied

    @property
    def last_mult_applied(self) -> float:
        """Último multiplicador efetivo usado (para daemon.state_full)."""
        return self._last_mult_applied

    def update_auto_state(
        self,
        auto_mult: float,
        change_at: float,
        *,
        mult_applied: float | None = None,
    ) -> None:
        """Atualiza o estado de debounce do modo "auto" e o mult efetivo aplicado.

        Encapsula a escrita dos campos privados `_last_auto_mult`,
        `_last_auto_change_at` e `_last_mult_applied`. Usado por chamadores
        externos (ex.: `_apply_rumble_policy` em `ipc_server.py`) que precisam
        propagar o resultado de `_effective_mult` de volta ao engine sem
        tocar atributos privados diretamente.

        Args:
            auto_mult: novo valor do debounce state de auto (último mult alvo
                confirmado pelo debounce). Para policies fixas, é o mesmo
                valor que entrou.
            change_at: timestamp da última mudança de debounce.
            mult_applied: (opcional) mult efetivo aplicado no hardware nesse
                ciclo. Para policy "auto", normalmente == auto_mult. Para
                policies fixas (economia/balanceado/max/custom), difere —
                nesse caso o chamador passa o mult efetivo aqui; se None,
                assume `auto_mult`.

        AUDIT-FINDING-RUMBLE-POLICY-DEDUP-01: substitui writeback direto em
        `rumble_engine._last_auto_*` / `._last_mult_applied` por método público.
        """
        self._last_auto_mult = auto_mult
        self._last_auto_change_at = change_at
        self._last_mult_applied = mult_applied if mult_applied is not None else auto_mult

    def _compute_mult(self, now: float) -> float:
        """Calcula multiplicador atual conforme política do config."""
        if self._config is None:
            return 1.0
        battery_pct = 50  # fallback neutro se estado indisponível
        if self._state_ref is not None:
            with contextlib.suppress(AttributeError, TypeError, ValueError):
                battery_pct = int(self._state_ref.battery_pct)

        mult, self._last_auto_mult, self._last_auto_change_at = _effective_mult(
            config=self._config,
            battery_pct=battery_pct,
            now=now,
            last_auto_mult=self._last_auto_mult,
            last_auto_change_at=self._last_auto_change_at,
        )
        return mult

    def _apply(self, cmd: RumbleCommand, now: float) -> RumbleCommand:
        mult = self._compute_mult(now)
        self._last_mult_applied = mult
        effective_weak = _clamp(round(cmd.weak * mult))
        effective_strong = _clamp(round(cmd.strong * mult))
        self._controller.set_rumble(weak=effective_weak, strong=effective_strong)
        self._last_applied = cmd
        self._last_applied_at = now
        self._pending = None
        return cmd

    @property
    def mult_applied(self) -> float:
        """Alias de last_mult_applied — conveniente para testes."""
        return self._last_mult_applied


def pedido_mais_forte(
    atual: tuple[int, int], novo: tuple[int, int]
) -> tuple[int, int]:
    """O maior de dois pedidos de vibração, comparado por INTENSIDADE.

    MASCARA-XBOX-MUDA-01 (09/08/2026). Os dois gamepads virtuais guardam "o
    maior pedido que o jogo fez" para responder a única pergunta que importa
    depois de "pediu?": **dava para SENTIR?**. Os dois guardavam-no com o
    operador de tupla do Python, que compara na ordem lexicográfica:

        (1, 0) > (0, 255)   # True — e é a resposta errada

    Um pedido de ``(0, 255)`` sacode o controle inteiro; ``(1, 0)`` não move
    nada. Com a comparação lexicográfica, um único pedido de motor fraco
    APAGA o registro de uma vibração máxima que veio antes, e o painel passa a
    dizer que o maior pedido do jogo foi imperceptível. É a armadilha nº 1
    desta casa (o instrumento mente mais que o produto) na sua forma mais
    barata: um operador que parecia óbvio.

    O critério é o motor mais forte do par; empate desempata pela soma (um
    pedido nos DOIS motores é mais forte que o mesmo pico num só). Dono único
    aqui, e não uma cópia por backend, porque duas comparações divergiriam na
    primeira mudança — a classe de defeito registrada nesta casa.
    """
    if (max(novo), sum(novo)) > (max(atual), sum(atual)):
        return novo
    return atual


def _clamp(value: int) -> int:
    if value < RUMBLE_MIN:
        return RUMBLE_MIN
    if value > RUMBLE_MAX:
        return RUMBLE_MAX
    return value


__all__ = [
    "DEFAULT_MIN_INTERVAL_SEC",
    "RUMBLE_MAX",
    "RUMBLE_MIN",
    "RumbleCommand",
    "RumbleEngine",
    "_effective_mult",
    "pedido_mais_forte",
    "teto_do_orcamento",
]
