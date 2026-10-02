"""A política de intensidade da vibração: o funil por onde passa todo pedido.

FEAT-RUMBLE-POLICY-01: política de intensidade global (economia/balanceado/
max/auto/custom) aplica multiplicador sobre weak e strong antes de enviar ao
hardware. O multiplicador do modo "auto" usa a bateria do estado mais recente
com debounce de 5s para evitar oscilação em limiar de threshold.

O funil é `_effective_mult`, e as três rotas de vibração o chamam:
`daemon.ipc_rumble_policy.apply_rumble_policy` (o `rumble.set` e o "Aplicar"),
`daemon.subsystems.rumble.reassert_rumble` (o rumble fixado, no tique) e
`daemon.subsystems.gamepad._game_rumble_mult` (o force-feedback do jogo). A
memória do debounce do "auto" é a do daemon (`_last_auto_mult` /
`_last_auto_change_at`).

O `RumbleEngine` (throttle de 50 Hz com `link()` e `tick()`) SAIU em 28/09/2026
(O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01): o daemon nunca o construiu, e o funil
acima o substituiu. As réguas que ele carregava passaram ao funil vivo.
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

#: CONFIG-05 (22/08/2026): a única chave de orçamento da mesa que IMPÕE teto
#: hoje. As outras três não impõem nenhum, e por dois motivos diferentes:
#: ``balanceado`` e ``max`` porque a dica delas promete, palavra por palavra,
#: *"tudo como o jogo pedir, sem teto"*; ``auto`` porque o teto dele seria
#: MÓVEL — muda a cada tique com a bateria —, e a casa já decidiu não prometer
#: número móvel na tela (`profiles/manager.py:1882-1888`, o pulo com log
#: `escala_de_vibracao_pulada_base_movel`).
#: PONTEIRO CORRIGIDO em 01/09/2026: ele dizia `:1556-1567`, que é o
#: `carimbar_ponte` — assunto inteiramente diferente, e quem o seguisse
#: concluiria que a cura não existe.
_ORCAMENTO_COM_TETO = "economia"


#: O QUE A TELA ESCREVE QUANDO ``teto_do_orcamento`` DEVOLVE ``None``. Mora aqui,
#: ao lado da função cujo ``None`` ela traduz, desde 01/09/2026 — antes vivia em
#: ``app/actions/config/secao_orcamento.py``, que puxa ``gi``/``Gtk`` no import
#: (por ``app.widgets.segmented_selector``, medido). Uma camada de tela sem GTK
#: que precisasse desta palavra tinha de escolher entre arrastar a janela inteira
#: para dentro do processo e digitar a frase de novo — e a segunda grafia é a que
#: fica para trás. ``secao_orcamento`` reexporta, então ``secao_orcamento.SEM_TETO``
#: continua valendo para quem já o lia.
#:
#: **Não é "100%"**: um percentual afirmaria um limite onde não há, e o "Máximo"
#: da aba Rumble entrega 150% justamente por não ter limite.
SEM_TETO = "Sem teto"


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
    (`profiles/manager.py:3549-3599`): o valor que chega ao backend já vem
    escalado pela política global, então o fator por unidade é RELATIVO — um
    produto mexeria na base daquela conta sem ninguém saber.

    PONTEIRO CORRIGIDO em 01/09/2026: ele dizia `:1541-1546`, que é o
    ``ponte_confirmada_do_appid``.
    """
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
    ``rumble_policy`` do ``state_full`` (`daemon/ipc_handlers.py:3439`), que é
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

    # AS DUAS FIXAS SAEM DE :func:`forca_do_global`, e não de uma conta escrita
    # aqui — 01/09/2026. A tela do teto por controle precisa do MESMO número
    # para dizer o que chega ao motor, e enquanto ele estivesse só aqui ela
    # teria de reescrevê-lo. É a razão pela qual o `?` da aba Conexões afirmava
    # "o global vale Sem teto" com o daemon cortando a 0,3.
    if policy == "custom" or policy in RUMBLE_POLICY_MULT:
        mult = forca_do_global(policy, orcamento, config.rumble_policy_custom_mult)
        if mult is not None:
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


__all__ = [
    "_effective_mult",
    "pedido_mais_forte",
    "teto_do_orcamento",
]
