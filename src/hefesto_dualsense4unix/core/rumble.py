"""A política de intensidade da vibração: o funil por onde passa todo pedido."""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

_ORCAMENTO_COM_TETO = "economia"

#: O degrau que a tela chama de «Padrão» (decisão de produto de 04/10/2026: o
#: Balanceado é o original, então o degrau «Original» não tem razão de
#: existir): a chave, a CLI e o perfil seguem
#: `balanceado`, e o multiplicador dele é 1,0 em `RUMBLE_POLICY_MULT`.
POLITICA_PADRAO = "balanceado"


def vale_o_padrao(politica: str | None) -> bool:
    """``True`` quando o degrau que vale é o Padrão: o jogo chega como mandou.

    **É A ÚNICA PERGUNTA** que as barras por canal (os dois motores e o ganho da
    háptica) fazem antes de se aplicar: em Padrão elas ficam guardadas e não
    multiplicam nada; em Economia, Máximo ou Personalizado elas voltam.
    """
    return politica == POLITICA_PADRAO


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
    ``rumble_policy`` do ``state_full`` (`daemon/ipc_handlers.py:2037`), que é
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
    mesmo. Quem mexer nesta escada mexe no texto que a promete na tela.

    **O TETO DO ORÇAMENTO DA MESA ENTRA AQUI, E SÓ AQUI** (CONFIG-05,
    22/08/2026). Este é o funil dos TRÊS caminhos de vibração do produto —
    ``ipc_rumble_policy.apply_rumble_policy`` (o ``rumble.set`` e o "Aplicar" do
    rodapé), ``subsystems.gamepad._game_rumble_mult`` (o force-feedback do
    JOGO) e ``subsystems.rumble.reassert_rumble`` (o tique de 200 ms do rumble
    fixado) —, então um ponto de aplicação basta para a POLÍTICA. As QUATRO
    saídas o respeitam, o fallback de política desconhecida inclusive: deixar
    uma de fora abriria um caminho em que o orçamento simplesmente não vale.

    **A FORÇA DE UM CONTROLE NÃO SAI DAQUI, sai de :func:`forca_do_controle`**
    (09/10/2026), que compõe esta política com a bateria DAQUELE controle e o
    fator da peça dele, e põe o teto do orçamento por último, como ``min``: o
    teto vence a peça (decisão por delegação).
    Esta função segue como a conta da política global, para quem pergunta sem
    controle (a tela, o resumo).

    **Teto, não troca**: o ``config.rumble_policy`` dela não é reescrito em
    lugar nenhum. Voltar o orçamento para Balanceado devolve o mult inteiro sem
    ela reclicar coisa alguma — é essa a invariante, e ela tem teste
    (``tests/unit/test_orcamento_e_teto_nao_troca.py``).
    """
    return _degrau_da_politica(
        config,
        _orcamento_declarado(config),
        battery_pct,
        now,
        last_auto_mult,
        last_auto_change_at,
        auto_debounce_sec,
    )


def _degrau_da_politica(
    config: DaemonConfig,
    orcamento: str | None,
    battery_pct: int,
    now: float,
    last_auto_mult: float,
    last_auto_change_at: float,
    auto_debounce_sec: float,
) -> tuple[float, float, float]:
    """O corpo de :func:`_effective_mult`, com o orçamento passado por quem chama.

    :func:`forca_do_controle` passa ``None`` para pôr o teto só no fim, depois
    do fator da peça.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import RUMBLE_POLICY_MULT

    policy = config.rumble_policy
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


#: A bateria de quem o backend ainda não leu: o degrau do meio do `auto`.
BATERIA_SEM_LEITURA = 50


def forca_do_controle(
    config: DaemonConfig,
    uniq: str | None,
    bateria: int | None,
    memoria: dict[str, tuple[float, float]],
    agora: float,
    *,
    escala: float | None = None,
    auto_debounce_sec: float = 5.0,
) -> float:
    """A fração do pedido que chega aos motores do controle ``uniq``.

    A-FORCA-DA-VIBRACAO-DE-CADA-CONTROLE-SAI-DE-UM-FUNIL-SO-COM-A-BATERIA-DELE-
    E-O-TETO-01 (09/10/2026). É o dono único da força de um controle, e os
    três caminhos de vibração (o gesto da tela, o par fixado do reassert e o
    rumble do jogo) chamam só ele. A conta, nesta ordem:

    1. a política viva, com a bateria DE ``uniq`` no ``auto`` (``None`` vale
       :data:`BATERIA_SEM_LEITURA`) e o debounce dele em ``memoria[uniq]``;
    2. vezes o fator da peça (``escala``), o que a peça escolheu sobre o global;
    3. o teto do orçamento da mesa por último, como ``min``: o Perfil
       Econômico poupa a bateria, e a peça em Máximo não o fura (decisão por
       delegação).

    ``memoria`` é mutada: guarda ``(âncora, instante)`` do ``auto`` por
    controle, e ``uniq`` ``None`` usa a chave vazia.
    """
    chave = uniq or ""
    ancora, quando = memoria.get(chave, (0.7, 0.0))
    mult, nova_ancora, novo_quando = _degrau_da_politica(
        config,
        None,
        BATERIA_SEM_LEITURA if bateria is None else int(bateria),
        agora,
        ancora,
        quando,
        auto_debounce_sec,
    )
    memoria[chave] = (nova_ancora, novo_quando)
    if escala is not None:
        mult *= float(escala)
    return _sob_o_teto(mult, teto_do_orcamento(_orcamento_declarado(config)))


def pedido_mais_forte(
    atual: tuple[int, int], novo: tuple[int, int]
) -> tuple[int, int]:
    """O maior de dois pedidos de vibração, comparado por INTENSIDADE."""
    if (max(novo), sum(novo)) > (max(atual), sum(atual)):
        return novo
    return atual


__all__ = [
    "BATERIA_SEM_LEITURA",
    "_effective_mult",
    "forca_do_controle",
    "pedido_mais_forte",
    "teto_do_orcamento",
]
