"""A política de intensidade da vibração: o funil por onde passa todo pedido."""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

_ORCAMENTO_COM_TETO = "economia"


SEM_TETO = "Sem teto"


def teto_do_orcamento(orcamento: str | None) -> float | None:
    """O teto que o orçamento da mesa impõe ao multiplicador, ou ``None``."""
    if orcamento != _ORCAMENTO_COM_TETO:
        return None
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    return RUMBLE_POLICY_MULT[_ORCAMENTO_COM_TETO]


def _sob_o_teto(mult: float, teto: float | None) -> float:
    """``mult`` limitado por ``teto`` — ``min``, **nunca** produto."""
    if teto is None:
        return mult
    return min(mult, teto)


def forca_do_global(
    policy: str | None,
    orcamento: str | None,
    custom_mult: float | None = None,
) -> float | None:
    """A fração do que o JOGO pediu que a política GLOBAL deixa passar hoje.

    É o multiplicador do funil, já sob o teto do orçamento da mesa — o mesmo
    número que :func:`_effective_mult` devolve para as políticas fixas, e por
    isso ele **é** este corpo: a função de baixo chama esta, e não uma cópia.
    Uma segunda conta aqui divergiria da do daemon no primeiro degrau que
    mudasse, e o preço já foi pago nesta casa (a dica que dizia 60% enquanto o
    produto cortava em 30).

    ``None`` quer dizer **não dá para responder com uma conta só**, e nunca
    "sem limite":

    * ``auto`` — o degrau muda com a bateria a cada tique. Prometer um número
      móvel na tela é a mesma razão pela qual
      ``_controllers_to_rumble_scales`` PULA a peça sob um global ``auto``;
    * ``custom`` sem ``custom_mult``, e política fora da tabela — quem chama
      não sabe o suficiente para afirmar nada.

    QUEM PERGUNTA PELA TELA TEM DE PASSAR A POLÍTICA **VIVA** — o
    ``rumble_policy`` do ``state_full`` (`daemon/ipc_handlers.py:2493`), que é
    o ``DaemonConfig.rumble_policy`` lido logo abaixo. A política do PERFIL não
    serve: `daemon/lifecycle.apply_profile_rumble_policy` deixa a política de
    origem MANUAL intocada quando o perfil não tem opinião, e aí as duas
    divergem com dois cliques.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    teto = teto_do_orcamento(orcamento)
    if policy == "custom":
        if custom_mult is None:
            return None
        return _sob_o_teto(float(custom_mult), teto)
    if policy in RUMBLE_POLICY_MULT:
        return _sob_o_teto(RUMBLE_POLICY_MULT[policy], teto)
    return None


def _orcamento_declarado(config: Any) -> str | None:
    """A chave do orçamento da mesa que vale AGORA, ou ``None``."""
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
    fixado) —, então um ponto de aplicação basta para a POLÍTICA. As QUATRO
    saídas o respeitam, o fallback de política desconhecida inclusive: deixar
    uma de fora abriria um caminho em que o orçamento simplesmente não vale.

    **O QUE ESTE FUNIL NÃO ALCANÇA, e a linha que dizia o contrário caiu em
    01/09/2026.** Ela afirmava que *"não há como um caminho escapar do teto"*.
    Há: a escala POR PEÇA (`POR-UNIDADE-01`) é aplicada um andar ABAIXO e
    DEPOIS deste ``min``, em ``core/backend_pydualsense._escalar_rumble``
    (`:3797-3818`), sobre o valor que já saiu daqui. Com o orçamento em
    ``economia`` (teto 0,3), o perfil global em ``economia`` e uma peça em
    ``max``, ``_controllers_to_rumble_scales`` publica ``1,5/0,3 = 5,0`` e o
    motor daquela peça recebe cinco vezes o que o teto prometeu.

    ESTÁ INERTE NA MESA DELA, medido em 01/09/2026: ``orcamento_em_vigor()``
    devolve ``None`` (o ``maquina.json`` não existe), e os 33 perfis não têm
    um único ``controllers[*].rumble``. **A aritmética não se toca aqui**:
    corrigi-la exige escolher entre saturar o produto no teto e fazer o fator
    ser ``min`` também, e as duas mudam o que o motor faz — é decisão dela, e é
    sprint própria.

    **Teto, não troca**: o ``config.rumble_policy`` dela não é reescrito em
    lugar nenhum. Voltar o orçamento para Balanceado devolve o mult inteiro sem
    ela reclicar coisa alguma — é essa a invariante, e ela tem teste
    (``tests/unit/test_orcamento_e_teto_nao_troca.py``).
    """
    from hefesto_dualsense4unix.daemon.lifecycle import RUMBLE_POLICY_MULT

    policy = config.rumble_policy
    orcamento = _orcamento_declarado(config)
    teto = teto_do_orcamento(orcamento)

    if policy == "custom" or policy in RUMBLE_POLICY_MULT:
        mult = forca_do_global(policy, orcamento, config.rumble_policy_custom_mult)
        if mult is not None:
            return mult, mult, last_auto_change_at

    if policy == "auto":
        if battery_pct > 50:
            target = 1.0
        elif battery_pct >= 20:
            target = 0.7
        else:
            target = 0.3

        target = _sob_o_teto(target, teto)

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
            return last_auto_mult, last_auto_mult, last_auto_change_at

        return last_auto_mult, last_auto_mult, last_auto_change_at

    fallback = _sob_o_teto(RUMBLE_POLICY_MULT["balanceado"], teto)
    logger.warning("rumble_policy_desconhecida", policy=policy)
    return fallback, fallback, last_auto_change_at


def pedido_mais_forte(
    atual: tuple[int, int], novo: tuple[int, int]
) -> tuple[int, int]:
    """O maior de dois pedidos de vibração, comparado por INTENSIDADE."""
    if (max(novo), sum(novo)) > (max(atual), sum(atual)):
        return novo
    return atual


__all__ = [
    "_effective_mult",
    "pedido_mais_forte",
    "teto_do_orcamento",
]
