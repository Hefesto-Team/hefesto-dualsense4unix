"""O roteador de movimento — o giroscópio vira algo que TODO jogo já lê.

MOVIMENTO-EM-QUALQUER-MASCARA-01 (21/09/2026), primeira entrega da camada 2 da
`ROTEADOR-DE-ENTRADA-01`. A tese é dela: *"universalizar todas as features do
dualsense independente do modo escolhido (…) a máscara é só pra enganar o
jogo"*.  <!-- noqa-acento: citação literal dela -->

O QUE ESTE ARQUIVO É: a regra inteira, pura. Recebe número, devolve número.
Sem I/O, sem thread, sem device. É o que deixa a régua exercitar a mira por
movimento inteira sem aparelho nenhum — a mesma disciplina do
`core/remapeamento_de_botao.py` e do `core/virtual_motion.py`.

O QUE ELE NÃO É, e a recusa é medida
------------------------------------
Não é "Xbox com giroscópio". Nenhuma linha daqui publica sensor: o `uinput` não
sabe declarar `uniq` (não há `UI_SET_UNIQ` no kernel) e sob Proton o evdev não
atravessa o `winebus`. O cabeçalho de `integrations/canal_sem_imu.py` já
escreveu isso em 17/09 e continua valendo. Este módulo **traduz**: velocidade
angular entra, deslocamento de analógico ou de cursor sai — e um analógico todo
jogo lê, inclusive os que nunca ouviram falar de DualSense.

ONDE A TRADUÇÃO ENTRA, e é um ponto só:

    `daemon/subsystems/gamepad.dispatch_gamepad`, logo antes de
    `device.forward_analog` — o mesmo lugar em que a troca botão a botão do
    perfil entra antes do `forward_buttons`.

O ESTADO ATIVO MORA NO `StateStore`, e pelo mesmo motivo medido em 13/09 que
pôs o remapeamento lá: das rotas que ativam perfil, a do boot
(`daemon/connection.py::restore_last_profile`) monta o `ProfileManager` à mão e
não recebe canal nenhum da fábrica — mas TODAS passam `store=daemon.store`.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields, replace
from types import MappingProxyType
from typing import Final

from hefesto_dualsense4unix.core.virtual_motion import REGISTRO, chave_de_sensor

#: Os destinos que o roteador conhece. `nenhum` existe para o perfil poder
#: dizer "desligado" sem apagar o resto do arranjo dela.
DESTINO_NENHUM: Final = "nenhum"
DESTINO_ANALOGICO_DIREITO: Final = "analogico_direito"
DESTINO_ANALOGICO_ESQUERDO: Final = "analogico_esquerdo"
DESTINO_MOUSE: Final = "mouse"
DESTINOS: Final[tuple[str, ...]] = (
    DESTINO_NENHUM,
    DESTINO_ANALOGICO_DIREITO,
    DESTINO_ANALOGICO_ESQUERDO,
    DESTINO_MOUSE,
)
#: O TOQUE E A INCLINAÇÃO COMO FONTE — NO-MODO-XBOX-TUDO-FUNCIONA-01 (28/09).
#: Os destinos de cada um; o resto da conta mora no fim do módulo.
TOQUE_CURSOR: Final = "cursor"
TOQUE_ZONAS: Final = "zonas"
TOQUES: Final[tuple[str, ...]] = (DESTINO_NENHUM, TOQUE_CURSOR, TOQUE_ZONAS)
DESTINOS_DA_INCLINACAO: Final[tuple[str, ...]] = (
    DESTINO_NENHUM,
    DESTINO_ANALOGICO_ESQUERDO,
    DESTINO_ANALOGICO_DIREITO,
)

#: QUAL EIXO DO GIRO VIRA O HORIZONTAL. Os nomes são a convenção do kernel
#: (`hid-playstation.c`: ABS_RX/RY/RZ = gyro x/y/z), e a escolha é de quem usa:
#: girar o controle como um volante (`roll`) e girar como uma cabeça (`yaw`)
#: são gestos diferentes, e pessoas diferentes alcançam um ou o outro. O caso do
#: amigo dela — mobilidade só na mão direita — é exatamente por isso que esta
#: constante existe em vez de um eixo fixo no código.
EIXO_YAW: Final = "yaw"      # GyroSnapshot.y — ABS_RY
EIXO_ROLL: Final = "roll"    # GyroSnapshot.z — ABS_RZ
EIXOS_HORIZONTAIS: Final[tuple[str, ...]] = (EIXO_YAW, EIXO_ROLL)

#: A faixa do eixo do gamepad virtual, na língua dos dois backends: 0-255 com
#: 128 no centro (`uinput_gamepad._capacidades_padrao`, e o mesmo no vpad uhid).
CENTRO_DO_EIXO: Final = 128
EIXO_MIN: Final = 0
EIXO_MAX: Final = 255
#: Deflexão máxima que o giro pode SOMAR a um eixo. 127 é o fundo do curso —
#: com o analógico físico parado no centro, sensibilidade cheia e o teto de
#: graus/s atingido, o jogo vê o stick no batente.
DEFLEXAO_MAXIMA: Final = 127

#: A ZONA MORTA, em graus/s. Um DualSense parado numa mesa não marca zero: o
#: giroscópio tem deriva, e sem corte a câmera do jogo passeia sozinha.
#:
#: **MEDIDO NO DUALSENSE DELA, 21/09/2026** — 60 amostras a 20 Hz, controle
#: parado na mesa: pior eixo (y) com média 0,72 e **máximo 0,85 graus/s**. Os
#: 3,0 cobrem a deriva com 3,5x de margem.
#:
#: **E A MORDIDA REVELOU O QUE ESTE NÚMERO FAZ DE VERDADE:** no padrão, NADA.
#: A curva (`EXPO_DO_GIRO`) mais o arredondamento do eixo já zeram tudo abaixo
#: de ~7 graus/s sozinhos — com 3,0 ou com 0,0 a saída é byte a byte a mesma. A
#: zona morta é a SEGUNDA linha de defesa contra a deriva, não a primeira.
#:
#: **ONDE ELA É A FEATURE INTEIRA: o tremor.** Este app é de acessibilidade, e
#: um tremor essencial mora na faixa de 15 a 30 graus/s — bem acima do que a
#: curva corta. Para essa pessoa, subir este dial (1 a 60 na tela) é o que
#: separa uma mira usável de uma câmera que treme junto com a mão. É por isso
#: que ele é CAMPO do arranjo, e não constante escondida.
#:
#: A régua que prova as duas metades é
#: `test_a_zona_morta_alta_e_o_dial_de_quem_tem_tremor`.
ZONA_MORTA_PADRAO_GRAUS_S: Final = 3.0
#: O TETO, em graus/s: a velocidade angular que já produz deflexão cheia. 220°/s
#: é um giro de pulso rápido; acima disso o eixo satura e a mira não acelera
#: mais. Também é campo.
TETO_PADRAO_GRAUS_S: Final = 220.0

SENSIBILIDADE_MIN: Final = 1
SENSIBILIDADE_MAX: Final = 12
SENSIBILIDADE_PADRAO: Final = 6

#: A CURVA. Achata a região logo acima da zona morta (ajuste fino) e preserva o
#: teto em velocidade cheia.
#:
#: NÃO É O `MOUSE_EXPO`, e a distinção importa: aquele molda a DEFLEXÃO de um
#: analógico em px/s; este molda VELOCIDADE ANGULAR em deflexão. Domínios
#: diferentes, número igual por enquanto — e importá-lo de
#: `integrations/uinput_mouse` arrastaria o módulo de uinput para o caminho
#: quente do jogo, que é a mesma razão pela qual `core/remapeamento_de_botao`
#: não importa `core/acoes_de_botao`.
EXPO_DO_GIRO: Final = 1.6

#: PIXELS POR GRAU do destino «mouse», na sensibilidade padrão. 12 px/grau põe
#: um giro de 90° em ~1080 px — uma tela 1080p inteira. O número CERTO é por
#: jogo (a sensibilidade interna do jogo entra na conta) e é da bancada dela;
#: por isso, de novo, é campo do arranjo.
PIXELS_POR_GRAU_PADRAO: Final = 12.0

#: Nome do atributo em que o arranjo ativo se pendura no `StateStore`. Literal
#: em um lugar só, como o `_ATRIBUTO_DO_ATIVO` do remapeamento.
_ATRIBUTO_DO_ATIVO: Final = "_roteador_de_movimento_ativo"


class ArranjoRecusadoError(ValueError):
    """O arranjo declarado no perfil não faz sentido — com o motivo no texto."""


@dataclass(frozen=True, slots=True)
class ArranjoDeMovimento:
    """UM arranjo de mira por movimento — imutável, e é o que viaja pelo store.

    `frozen=True` não é estilo: o poll loop lê este objeto noutra thread a cada
    tique enquanto o event loop do IPC pode estar trocando o arranjo inteiro
    por causa de uma troca de perfil. Congelado, a troca é só a troca de uma
    referência, que é atômica — ninguém muda um campo por baixo de um tique em
    curso. É a mesma razão pela qual o remapeamento viaja em `MappingProxyType`.
    """

    destino: str = DESTINO_NENHUM
    sensibilidade: int = SENSIBILIDADE_PADRAO
    eixo_horizontal: str = EIXO_YAW
    inverter_horizontal: bool = False
    inverter_vertical: bool = False
    zona_morta_graus_s: float = ZONA_MORTA_PADRAO_GRAUS_S
    teto_graus_s: float = TETO_PADRAO_GRAUS_S
    pixels_por_grau: float = PIXELS_POR_GRAU_PADRAO
    #: O BOTÃO QUE LIGA. `None` = sempre ligado. Um id do vocabulário do jogo
    #: (`core/remapeamento_de_botao.REMAPEAVEIS`) = a mira só anda enquanto ele
    #: estiver apertado, que é como quem joga com giro de verdade usa (o
    #: "ativar ao mirar"). O PS não entra: ele é a saída de emergência dela.
    gatilho: str | None = None
    #: O que o touchpad faz (`TOQUES`) e para onde a inclinação vai
    #: (`DESTINOS_DA_INCLINACAO`) — os dois arranjos da resposta dela de 28/09.
    toque: str = DESTINO_NENHUM
    acelerometro: str = DESTINO_NENHUM

    @property
    def ligado(self) -> bool:
        """A MIRA (o giro) anda? `nenhum` é arranjo guardado e desligado.

        Continua sendo a pergunta do GIROSCÓPIO, e só dele: o chip «Mira
        Virtual», o filtro do report e a Navegação a fazem. Se o arranjo tem
        QUALQUER rota ligada — o giro, o toque ou a inclinação —, quem responde
        é :attr:`roteia`.
        """
        return self.destino != DESTINO_NENHUM and self.destino in DESTINOS

    @property
    def toca(self) -> bool:
        """O touchpad desta peça vai ao cursor ou às zonas (NO-MODO-XBOX, 28/09)."""
        return self.toque in (TOQUE_CURSOR, TOQUE_ZONAS)

    @property
    def inclina(self) -> bool:
        """A inclinação desta peça move um analógico (NO-MODO-XBOX, 28/09)."""
        return self.acelerometro in (DESTINO_ANALOGICO_ESQUERDO, DESTINO_ANALOGICO_DIREITO)

    @property
    def roteia(self) -> bool:
        """Alguma rota anda: o giro, o toque ou a inclinação.

        É a pergunta dos laços do tique (`ativo`, `da_peca`): sem ela, a peça
        que só pediu o toque em zonas ficaria fora do motor, porque o destino
        do giro dela é `nenhum`.
        """
        return self.ligado or self.toca or self.inclina

    @property
    def quer_angulo(self) -> bool:
        """Este destino consome ÂNGULO percorrido (mouse) em vez de velocidade.

        A distinção não é detalhe de implementação, é física: um analógico é
        uma POSIÇÃO — a deflexão tem de ser proporcional à velocidade angular,
        senão a câmera continuaria virando com o controle parado. O cursor é um
        DESLOCAMENTO — ele quer o ângulo percorrido desde o último tique, e é
        por isso que o `MotionSensorReader` precisa integrar (E3) em vez de
        multiplicar a velocidade pelo período do tique: um giro rápido entre
        dois tiques de 60 Hz seria cortado pela metade.
        """
        return self.destino == DESTINO_MOUSE


def _componentes(
    giro: tuple[float, float, float], arranjo: ArranjoDeMovimento
) -> tuple[float, float]:
    """Os três eixos do sensor viram (horizontal, vertical), já com o sinal.

    `giro` é `(x, y, z)` como o `GyroSnapshot` entrega — ABS_RX/RY/RZ do nó
    «Motion Sensors», em graus/s. O vertical é sempre o `x` (o pitch: levantar
    e baixar o nariz do controle); o horizontal é escolha do arranjo.

    O SINAL É DA BANCADA, NÃO DAQUI. Qual lado do giro é "para a direita"
    depende de como a pessoa segura o controle, e é a primeira coisa que ela
    corrige em dez segundos com `inverter_horizontal`. Fixar um sinal aqui e
    chamá-lo de certo seria afirmar sobre a mão dela.
    """
    gx, gy, gz = giro
    horizontal = gz if arranjo.eixo_horizontal == EIXO_ROLL else gy
    vertical = gx
    if arranjo.inverter_horizontal:
        horizontal = -horizontal
    if arranjo.inverter_vertical:
        vertical = -vertical
    return horizontal, vertical


def _fator_radial(
    horizontal: float, vertical: float, arranjo: ArranjoDeMovimento
) -> float:
    """0.0 a 1.0: quanto do curso do eixo este movimento merece.

    Normalização RADIAL, e não eixo a eixo, pela mesma razão que o cursor do
    stick usa (`uinput_mouse._compute_move_px_per_sec`): com deadzone por eixo
    um movimento diagonal lento atravessa a zona morta em um eixo e não no
    outro, e a mira "engancha" nas diagonais. Medido em outro lugar da casa,
    herdado aqui de propósito.
    """
    magnitude = math.hypot(horizontal, vertical)
    zona = max(0.0, arranjo.zona_morta_graus_s)
    if magnitude <= zona:
        return 0.0
    faixa = arranjo.teto_graus_s - zona
    if faixa <= 0.0:
        # Teto abaixo da zona morta: arranjo torto que o esquema já recusa.
        # Aqui, em vez de dividir por zero no caminho do jogo, vale tudo.
        return 1.0
    return float(min(1.0, (magnitude - zona) / faixa) ** EXPO_DO_GIRO)


def deflexao(
    giro: tuple[float, float, float], arranjo: ArranjoDeMovimento
) -> tuple[int, int]:
    """Velocidade angular (graus/s) → deslocamento a SOMAR num analógico.

    Devolve `(dh, dv)` em unidades de eixo (-127..127), já com a curva, a zona
    morta, o teto e a sensibilidade aplicados. `(0, 0)` é resposta legítima e
    frequente: é o controle parado na mesa.

    O ARRANJO DESLIGADO NÃO MOVE NADA — A-MIRA-POR-MOVIMENTO-NA-TELA-01. Até
    23/09 o destino não entrava na conta, e um arranjo `nenhum` que chegasse
    aqui movia o analógico direito como se fosse ele. Não chegava, porque o
    `ativo()` o barrava; desde que a mira passou a ser POR PEÇA, o `ativo()`
    devolve :data:`SO_NAS_PECAS` (que é `nenhum`) para a mesa em que só alguns
    controles miram, e é esta linha que o torna inerte em qualquer motor que
    ainda não pergunte pela peça.
    """
    if not arranjo.ligado:
        return 0, 0
    horizontal, vertical = _componentes(giro, arranjo)
    fator = _fator_radial(horizontal, vertical, arranjo)
    if fator <= 0.0:
        return 0, 0
    magnitude = math.hypot(horizontal, vertical)
    alcance = fator * DEFLEXAO_MAXIMA * (arranjo.sensibilidade / SENSIBILIDADE_MAX)
    return (
        round(alcance * horizontal / magnitude),
        round(alcance * vertical / magnitude),
    )


def _saturar(valor: int) -> int:
    """O eixo nunca sai de 0..255 — o kernel clampa, mas quem afirma é a casa."""
    return max(EIXO_MIN, min(EIXO_MAX, valor))


def misturar(eixo_h: int, eixo_v: int, dh: int, dv: int) -> tuple[int, int]:
    """Soma o giro ao analógico FÍSICO, com saturação.

    SOMA, NÃO SUBSTITUI, e é decisão de desenho com razão: quem usa as duas
    mãos quer mirar com o stick E corrigir com o giro (é como o Steam Input e o
    JoyShockMapper fazem); quem usa uma mão só tem o stick parado e a soma é
    idêntica a substituir. Substituir tiraria o stick de quem o tem.

    O centro FÍSICO daquela peça é preservado de graça: somamos ao valor cru,
    que já vem com a posição de repouso real do analógico dela — um controle
    que descansa em 130 continua descansando em 130.
    """
    return _saturar(eixo_h + dh), _saturar(eixo_v + dv)


def pixels(
    angulo: tuple[float, float, float], arranjo: ArranjoDeMovimento
) -> tuple[float, float]:
    """Ângulo percorrido (graus) → deslocamento de cursor, em pixels FLOAT.

    Float de propósito: quem trunca é quem emite, guardando o resto sub-pixel
    (`UinputMouseDevice.emit_gyro_move`, E6). Truncar aqui faria todo movimento
    lento virar zero para sempre — o defeito que o carry do cursor do stick já
    curou uma vez nesta casa.
    """
    if not arranjo.ligado:
        return 0.0, 0.0
    horizontal, vertical = _componentes(angulo, arranjo)
    fator = arranjo.pixels_por_grau * (arranjo.sensibilidade / SENSIBILIDADE_PADRAO)
    return horizontal * fator, vertical * fator


def montar(secao: object) -> ArranjoDeMovimento:
    """A seção do perfil vira arranjo SEMPRE — inclusive com o destino `nenhum`.

    A-MIRA-POR-MOVIMENTO-NA-TELA-01 (24/09/2026): substituiu o `resolver`, que
    devolvia `None` para o desligado. Os deslizantes da Calibrar mostram a
    sensibilidade e o «Ignorar tremor até» de um controle cuja mira está
    DESLIGADA, e o número que ela ajustou não pode sumir só porque a mira não
    está andando. O arranjo `nenhum` guarda os parâmetros e não move nada:
    `ligado` é falso, `ativo()` não o entrega ao tique, e `deflexao`/`pixels`
    devolvem zero.

    LEVANTA `ArranjoRecusadoError` no que o esquema deixaria passar mas o motor
    não sabe fazer — destino desconhecido, eixo desconhecido, teto abaixo da
    zona morta. Quem chama (`ProfileManager.apply_movimento` e
    `arranjo_da_peca`) trata a recusa desligando só aquela seção: as luzes e os
    gatilhos dela não pagam por uma linha torta, que é o contrato do
    `apply_remapeamento`.
    """
    destino = str(getattr(secao, "destino", DESTINO_NENHUM) or DESTINO_NENHUM)
    if destino not in DESTINOS:
        raise ArranjoRecusadoError(
            f"destino desconhecido: {destino!r} (conhecidos: {', '.join(DESTINOS)})"
        )
    eixo = str(getattr(secao, "eixo_horizontal", EIXO_YAW) or EIXO_YAW)
    if eixo not in EIXOS_HORIZONTAIS:
        raise ArranjoRecusadoError(
            f"eixo horizontal desconhecido: {eixo!r} "
            f"(conhecidos: {', '.join(EIXOS_HORIZONTAIS)})"
        )
    zona = float(getattr(secao, "zona_morta_graus_s", ZONA_MORTA_PADRAO_GRAUS_S))
    teto = float(getattr(secao, "teto_graus_s", TETO_PADRAO_GRAUS_S))
    if teto <= zona:
        raise ArranjoRecusadoError(
            f"teto ({teto}°/s) tem de ser maior que a zona morta ({zona}°/s)"
        )
    sens = int(getattr(secao, "sensibilidade", SENSIBILIDADE_PADRAO))
    # O TOQUE E A INCLINAÇÃO (NO-MODO-XBOX-TUDO-FUNCIONA-01, 28/09): a mesma
    # recusa do destino, para o que o esquema deixaria passar por `model_copy`.
    toque = str(getattr(secao, "toque", DESTINO_NENHUM) or DESTINO_NENHUM)
    if toque not in TOQUES:
        raise ArranjoRecusadoError(
            f"toque desconhecido: {toque!r} (conhecidos: {', '.join(TOQUES)})"
        )
    inclinacao = str(getattr(secao, "acelerometro", DESTINO_NENHUM) or DESTINO_NENHUM)
    if inclinacao not in DESTINOS_DA_INCLINACAO:
        raise ArranjoRecusadoError(
            f"destino da inclinação desconhecido: {inclinacao!r} "
            f"(conhecidos: {', '.join(DESTINOS_DA_INCLINACAO)})"
        )
    return ArranjoDeMovimento(
        destino=destino,
        sensibilidade=max(SENSIBILIDADE_MIN, min(SENSIBILIDADE_MAX, sens)),
        eixo_horizontal=eixo,
        inverter_horizontal=bool(getattr(secao, "inverter_horizontal", False)),
        inverter_vertical=bool(getattr(secao, "inverter_vertical", False)),
        zona_morta_graus_s=zona,
        teto_graus_s=teto,
        pixels_por_grau=float(
            getattr(secao, "pixels_por_grau", PIXELS_POR_GRAU_PADRAO)
        ),
        gatilho=(getattr(secao, "gatilho", None) or None),
        toque=toque,
        acelerometro=inclinacao,
    )


def definir_ativo(dono: object, arranjo: ArranjoDeMovimento | None) -> None:
    """Guarda o arranjo ATIVO no dono (o `StateStore`). `None` = sem mira.

    `None` É METADE DO CONTRATO, e é a metade que se esquece: o perfil sem
    arranjo APAGA o do perfil anterior. Sem isto, a mira que ela montou para um
    jogo continuaria valendo no jogo seguinte — que é exatamente a forma do
    CAMINHO-CONTAGIO-01, o defeito que fez o PRAGMATA perder a IMU por herança.
    """
    if dono is None:
        return
    setattr(dono, _ATRIBUTO_DO_ATIVO, arranjo if arranjo is not None else None)


def ativo(dono: object) -> ArranjoDeMovimento | None:
    """O arranjo ativo, ou `None`. Custo de dois `getattr` no caminho do jogo.

    SÓ UM `ArranjoDeMovimento` DE VERDADE VALE: um dublê feito de `MagicMock`
    responde qualquer atributo com outro mock, e um mock no caminho do jogo
    somaria um `Mock` a um inteiro e derrubaria o tique inteiro do controle. A
    checagem de tipo é a mesma trava do `remapeamento_de_botao.ativo`, e pelo
    mesmo susto.
    """
    valor = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if _roteia(valor):
        return valor
    # A MESA EM QUE SÓ ALGUNS CONTROLES MIRAM — A-MIRA-POR-MOVIMENTO-NA-TELA-01.
    # Os dois laços do tique (`gamepad.dispatch_gamepad` e
    # `coop.CoopManager.forward_all`) só chamam o motor quando esta função
    # devolve alguma coisa. Sem mira no perfil e com o chip «Mira Virtual»
    # aceso no P3, um `None` aqui calaria o P3 junto com a mesa. Quem decide
    # QUAL peça mira é o `da_peca`, chamado pelo motor com o `uniq` na mão.
    if any(_roteia(v) for v in por_peca(dono).values()):
        return SO_NAS_PECAS
    return None


# ---------------------------------------------------------------------------
# A MIRA POR PEÇA — A-MIRA-POR-MOVIMENTO-NA-TELA-01, 23/09/2026
# ---------------------------------------------------------------------------
#
# A palavra dela, a segunda do dia: *"Cria um botão virtual ao lado de
# giroscopio e acelerometro chamado Mira Virtual"* — no cartão de CADA
# controle. A primeira entrega deste módulo guardava UM arranjo por perfil
# (`D-0809-A-NAVEGACAO-E-GLOBAL-NO-PERFIL`), e a própria sprint-mãe deixou a
# porta escrita: *"o override por controle entra em `ControllerOverrides` sem
# migração: os campos são os mesmos"*. Entrou.  <!-- noqa-acento: citação literal dela -->
#
# A ORDEM DE DECISÃO É UMA SÓ: a peça que tem opinião usa a dela, campo a
# campo por cima da do perfil; a peça calada segue a do perfil. É a mesma
# regra do `leds` e do `rumble` por controle (PERFIL-01, merge POR CAMPO).
#
# O MAPA MORA NO `StateStore`, ao lado do arranjo da mesa, pelo mesmo motivo
# medido do `_ATRIBUTO_DO_ATIVO`: todas as rotas de ativação passam `store`.
# Ele viaja em `MappingProxyType` e é TROCADO inteiro, nunca editado: o tique
# o lê noutra thread, e a troca de uma referência é atômica.

#: Nome do atributo do mapa por peça no `StateStore`.
_ATRIBUTO_POR_PECA: Final = "_roteador_de_movimento_por_peca"

#: A mesa sem mira no perfil e com mira em alguma peça — ver `ativo()`. É um
#: arranjo `nenhum`: se um motor que ainda não pergunta pela peça o receber,
#: ele não move nada (`deflexao` e `pixels` devolvem zero para o desligado).
SO_NAS_PECAS: Final = ArranjoDeMovimento()

#: Os nove campos do arranjo, na língua do esquema — são os mesmos nomes em
#: `ProfileMovimentoConfig`, e é isso que deixa a peça sobrepor a mesa campo a
#: campo sem tradução nenhuma.
CAMPOS: Final[tuple[str, ...]] = tuple(f.name for f in fields(ArranjoDeMovimento))

_VAZIO: Final[Mapping[str, ArranjoDeMovimento | None]] = MappingProxyType({})


def _ligado(valor: object) -> bool:
    """Só um `ArranjoDeMovimento` de verdade, com a MIRA (o giro) ligada."""
    return type(valor) is ArranjoDeMovimento and valor.ligado


def _toca(valor: object) -> bool:
    """Só um `ArranjoDeMovimento` de verdade, com o touchpad no cursor ou nas zonas."""
    return type(valor) is ArranjoDeMovimento and valor.toca


def _roteia(valor: object) -> bool:
    """Só um `ArranjoDeMovimento` de verdade, com alguma rota — a trava do tique."""
    return type(valor) is ArranjoDeMovimento and valor.roteia


def _campos_escritos(secao: object) -> dict[str, object]:
    """Os campos que a seção DIZ — só os escritos, quando ela sabe distinguir.

    Um modelo do pydantic sabe (`model_fields_set`): o override da peça que só
    escreveu a sensibilidade não pode apagar o destino do perfil com o default
    `nenhum`. Qualquer outra coisa (o arranjo da mesa, um `SimpleNamespace`)
    responde por todos os campos que tiver.
    """
    if secao is None:
        return {}
    escritos = getattr(secao, "model_fields_set", None)
    nomes = CAMPOS if escritos is None else tuple(n for n in CAMPOS if n in escritos)
    return {n: getattr(secao, n) for n in nomes if hasattr(secao, n)}


class _Secao:
    """Uma seção montada à mão: só atributos, na forma que `montar` lê."""

    def __init__(self, campos: Mapping[str, object]) -> None:
        self.__dict__.update(campos)


def arranjo_da_peca(secao_da_mesa: object, secao_da_peca: object) -> ArranjoDeMovimento:
    """O arranjo de UMA peça: a seção dela campo a campo por cima da do perfil.

    Devolve SEMPRE um arranjo (o `montar`), inclusive desligado: é o que guarda
    a sensibilidade e o tremor que ela ajustou num controle cuja mira está
    apagada. Levanta `ArranjoRecusadoError` como o `montar`.
    """
    campos = _campos_escritos(secao_da_mesa)
    campos.update(_campos_escritos(secao_da_peca))
    return montar(_Secao(campos))


def por_peca(dono: object) -> Mapping[str, ArranjoDeMovimento | None]:
    """O mapa `{chave da peça: arranjo}` — vazio quando ninguém tem opinião."""
    valor = getattr(dono, _ATRIBUTO_POR_PECA, None)
    return valor if isinstance(valor, Mapping) else _VAZIO


def definir_por_peca(
    dono: object, mapa: Mapping[str, ArranjoDeMovimento | None] | None
) -> None:
    """TROCA o mapa inteiro. `None` ou vazio = nenhuma peça tem opinião.

    Vazio É METADE DO CONTRATO, como o `None` do `definir_ativo`: o perfil sem
    mira por peça APAGA a do perfil anterior. Sem isso o P3 do jogo de ontem
    continuaria mirando no jogo de hoje — a forma do CAMINHO-CONTAGIO-01.

    `None` como VALOR é legítimo e quer dizer *"esta peça tem opinião e ela é
    desligada"* — o arranjo que o motor recusou, por exemplo.
    """
    if dono is None:
        return
    limpo = {chave_de_sensor(k): v for k, v in (mapa or {}).items() if chave_de_sensor(k)}
    setattr(dono, _ATRIBUTO_POR_PECA, MappingProxyType(limpo))


def definir_da_peca(
    dono: object, uniq: str, arranjo: ArranjoDeMovimento | None, *, tem_opiniao: bool = True
) -> None:
    """Troca a opinião de UMA peça, e só dela — o gesto do chip, ao vivo.

    `tem_opiniao=False` tira a peça do mapa: ela volta a seguir o perfil.
    """
    chave = chave_de_sensor(uniq)
    if dono is None or not chave:
        return
    novo = dict(por_peca(dono))
    if tem_opiniao:
        novo[chave] = arranjo
    else:
        novo.pop(chave, None)
    setattr(dono, _ATRIBUTO_POR_PECA, MappingProxyType(novo))


def da_peca(
    dono: object, uniq: str | None, arranjo_da_mesa: object
) -> ArranjoDeMovimento | None:
    """O arranjo que vale para a peça `uniq` AGORA, ou `None` (nenhuma rota).

    Desde 28/09 (NO-MODO-XBOX-TUDO-FUNCIONA-01) a peça que só toca ou só
    inclina também volta daqui: quem pergunta pela MIRA confere `ligado`.

    É a pergunta que o motor faz com o `uniq` na mão, uma vez por tique e por
    controle: a opinião da peça, se ela tem; senão, o arranjo da mesa que o
    laço do tique já leu (`arranjo_da_mesa`, o que o `ativo()` devolveu). Com a
    mesa em :data:`SO_NAS_PECAS`, a peça calada não mira.

    Custo no caso comum (ninguém com opinião): um `getattr` e um `len`.
    """
    mapa = por_peca(dono)
    if mapa and uniq:
        chave = chave_de_sensor(uniq)
        if chave in mapa:
            valor = mapa[chave]
            return valor if _roteia(valor) else None
    return arranjo_da_mesa if _roteia(arranjo_da_mesa) else None  # type: ignore[return-value]


def parametros_da_peca(dono: object, uniq: str | None) -> ArranjoDeMovimento:
    """O arranjo desta peça MESMO DESLIGADO — o que os deslizantes mostram.

    A peça com opinião mostra a dela; a calada mostra a do perfil (o arranjo da
    mesa, guardado inteiro pelo `ProfileManager.apply_movimento`, ligado ou
    não); sem nenhum dos dois, os padrões deste módulo.
    """
    mapa = por_peca(dono)
    if uniq:
        valor = mapa.get(chave_de_sensor(uniq))
        if type(valor) is ArranjoDeMovimento:
            return valor
    mesa = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if type(mesa) is ArranjoDeMovimento:
        return mesa
    return ArranjoDeMovimento()


def sincronizar_o_filtro(dono: object) -> None:
    """Diz ao braço do REPORT quais peças estão mirando — o giro nativo sai delas.

    **A CÂMERA NÃO ANDA EM DOBRO** — ordem dela, 23/09/2026. No caminho `uhid`
    o jogo recebe o giro nativo pela janela de motion do vpad, e o jogo que o
    lê (o PRAGMATA) veria o mesmo gesto DUAS vezes: pelo giroscópio e pelo
    analógico direito. A decisão, medida pela régua que monta a janela: a peça
    que mira deixa de mandar o GIROSCÓPIO ao jogo como giroscópio — ele passa a
    chegar como analógico. O acelerômetro e o touchpad seguem intocados.

    O filtro roda na thread do report (~250 Hz) e não enxerga o `store`; por
    isso a conta é feita AQUI, de onde o arranjo mora, e o resultado desce ao
    `virtual_motion.REGISTRO`, que é o dono do filtro. Quem chama esta função
    é quem acabou de mexer no arranjo: o `apply_movimento` do gerente e o
    `mira.set` do IPC — nunca o tique.
    """
    if dono is None:
        return
    mesa = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    pecas = por_peca(dono)
    REGISTRO.definir_roteados(
        sem_chip=_ligado(mesa),
        por_peca={chave: _ligado(v) for chave, v in pecas.items()},
        # O TOQUE TAMBÉM (NO-MODO-XBOX-TUDO-FUNCIONA-01, 28/09): a peça cujo
        # touchpad vai ao cursor ou às zonas deixa de mandar o dedo ao jogo
        # pela janela do `uhid` — o mesmo toque não chega duas vezes.
        toque_sem_chip=_toca(mesa),
        toque_por_peca={chave: _toca(v) for chave, v in pecas.items()},
    )


# ---------------------------------------------------------------------------
# A MIRA NA NAVEGAÇÃO — A-MIRA-NA-NAVEGACAO-01, 24/09/2026
# ---------------------------------------------------------------------------
#
# A frase dela é *"A exceção do nativo todo o resto deve ter mira Virtual"*, e
# a decisão (`D-2409-NA-NAVEGACAO-O-GIRO-VIRA-CURSOR`) é a leitura literal: na
# Navegação não há controle virtual, e o giro de quem está com a Mira acesa
# move o cursor do computador. O motor já sabia o destino «mouse»; o que falta
# é dizer que, na Navegação, TODO destino ligado é o cursor — porque o
# analógico que ele escolheria é, ali, a roda e o cursor do próprio mouse.


def para_o_cursor(arranjo: ArranjoDeMovimento) -> ArranjoDeMovimento:
    """O mesmo arranjo, com o cursor por destino — o que a Navegação faz com ele.

    A sensibilidade, o «Ignorar tremor até», o «Só enquanto eu segurar» e os
    dois «Inverter» ficam como ela os deixou: só o destino muda. O arranjo
    desligado continua desligado — a peça de chip apagado não passa a mirar
    por estar na Navegação.
    """
    if not arranjo.ligado or arranjo.destino == DESTINO_MOUSE:
        return arranjo
    return replace(arranjo, destino=DESTINO_MOUSE)


def pecas_que_miram(dono: object) -> tuple[str, ...]:
    """As chaves das peças cuja OPINIÃO acende a mira — o chip de cada controle.

    Na Navegação não há laço de secundários (o co-op só existe com o controle
    virtual de pé), e quem pergunta pelo giro dos P2 a P4 precisa saber quais
    peças pedir. As peças sem opinião seguem a mira do perfil, e essas vêm da
    lista de conectados — não daqui.
    """
    return tuple(chave for chave, valor in por_peca(dono).items() if _ligado(valor))


#: A DRENAGEM QUE VEM DEPOIS DE UM SILÊNCIO NÃO É MOVIMENTO, em segundos.
#:
#: O acumulador de ângulo do leitor (`MotionSensorReader`) integra o giro a
#: cada pacote, e só zera quando alguém drena. Com o giro no cursor, o dono da
#: drenagem é o tique — e o tique para de drenar em três casos reais: a Mira
#: apagada (a peça não pede ângulo), o modo com controle virtual (o destino é o
#: analógico, que não pede ângulo) e a pausa ou o grace do laço. O leitor segue
#: aberto em todos, porque o cartão da tela lê o giro a 10 Hz.
#:
#: A PRIMEIRA DRENAGEM DEPOIS DISSO é o percurso inteiro do intervalo — com a
#: deriva de 0,72 graus/s medida no controle dela parado, dez minutos são
#: 430 graus, e a 12 px por grau o cursor saltaria cinco mil pixels no primeiro
#: gesto. É o defeito que o touchpad já pagou (`discard_touchpad_motion`, o
#: SALTO de cursor quando a emulação voltava) e que o teto do leitor
#: (`_TETO_DO_ANGULO_GRAUS`, cem voltas) não evita.
#:
#: MEIO SEGUNDO é trinta tiques de 60 Hz: um tique atrasado pelo laço não perde
#: movimento, e o que se descarta na volta de um silêncio é no máximo o giro de
#: meio segundo — sob a deriva, 0,4 grau.
SILENCIO_DA_DRENAGEM_S: Final = 0.5

#: O mapa `{chave da peça: instante da última drenagem}`, no `StateStore`. Só o
#: tique o toca (o `dispatch_gamepad`, o `forward_all` e o `dispatch_mouse`
#: rodam todos no laço do daemon), e por isso é um `dict` comum.
_ATRIBUTO_DA_DRENAGEM: Final = "_roteador_de_movimento_ultima_drenagem"


def angulo_do_tique(
    dono: object,
    uniq: str,
    angulo: tuple[float, float, float],
    agora: float,
) -> tuple[float, float, float] | None:
    """O ângulo que a peça acabou de drenar, ou `None` se ele é um acumulado.

    `None` quando a drenagem anterior desta peça foi há mais de
    :data:`SILENCIO_DA_DRENAGEM_S` (ou nunca houve): o ângulo drenado é o que
    se juntou enquanto ninguém drenava, e vira nada em vez de um salto. A
    drenagem em si já aconteceu — quem chama drena ANTES de perguntar —, então
    o tique seguinte começa do zero.

    Sem dono (o `store` que não há) a resposta é o próprio ângulo: sem onde
    guardar o relógio não há como saber, e é o comportamento de antes.
    """
    if dono is None:
        return angulo
    chave = chave_de_sensor(uniq)
    mapa = getattr(dono, _ATRIBUTO_DA_DRENAGEM, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DA_DRENAGEM, mapa)
    anterior = mapa.get(chave)
    mapa[chave] = agora
    if anterior is None or agora - anterior > SILENCIO_DA_DRENAGEM_S:
        return None
    return angulo


# ---------------------------------------------------------------------------
# O TOQUE E A INCLINAÇÃO — NO-MODO-XBOX-TUDO-FUNCIONA-01, 28/09/2026
# ---------------------------------------------------------------------------
#
# A resposta dela às perguntas 1 a 3 da sprint, ~16h50, em escolhas: **os
# dois** arranjos, por perfil de jogo, e quem valida é ela. (a) o touchpad move
# o cursor e o acelerômetro vira analógico, um chip por controle como a Mira
# Virtual; (b) o touchpad em zonas vira botões (direcional, L1, L2), para quem
# não os alcança. Este bloco é a regra pura dos dois; o motor que a chama é
# `daemon/subsystems/gamepad.py` (`aplicar_o_toque` e `aplicar_o_movimento`).
#
# ONDE ELES VALEM, decidido pelo padrão dela (o que custa menos a quem joga): onde
# há controle virtual — o modo DualSense e o modo Xbox, do P1 ao P4, no cabo e no
# rádio. Na Navegação o touchpad continua sendo o do computador
# (TOUCHPAD-DO-SISTEMA-01) e a inclinação não move nada: lá não há analógico de
# jogo, e o dedo já é o ponteiro. No Nativo, como a Mira, não há onde escrever.

#: A INCLINAÇÃO que não move nada, em graus. Um controle na mão nunca fica no
#: mesmo ângulo: seis graus deixam a mão respirar sem o personagem andar.
ZONA_MORTA_DA_INCLINACAO_GRAUS: Final = 6.0
#: A inclinação que já vale o analógico no batente, na sensibilidade padrão. A
#: sensibilidade encurta ou alonga este teto (12 = metade, 1 = seis vezes).
TETO_DA_INCLINACAO_GRAUS: Final = 30.0
#: O módulo mínimo, em g, para a leitura valer: abaixo disso o controle está
#: caindo ou o leitor ainda não leu, e não há gravidade de onde tirar ângulo.
GRAVIDADE_MINIMA_G: Final = 0.2

#: PIXELS POR UNIDADE DO TOUCHPAD na sensibilidade padrão. É o número do cursor
#: da Navegação (`uinput_mouse.TOUCHPAD_SENSITIVITY`), repetido aqui porque este
#: módulo é puro e o `uinput_mouse` arrastaria o uinput para o caminho do jogo —
#: a régua confere que os dois são o mesmo.
PIXELS_POR_UNIDADE_DO_TOQUE: Final = 0.45

#: AS ZONAS. Os dois terços da esquerda são o direcional; o terço da direita,
#: em cima o L1 e embaixo o L2 — a ordem dos dois no plástico. No direcional, o
#: miolo não aperta nada, e a direção é por setor de 45 graus: os quatro do
#: meio de cada lado são uma direção, os quatro dos cantos são duas.
FRACAO_DO_DIRECIONAL: Final = 2.0 / 3.0
MIOLO_DO_DIRECIONAL: Final = 0.12
BOTAO_DA_ZONA_DE_CIMA: Final = "l1"
#: O L2 na língua do LEITOR (`remapeamento_de_botao.GATILHOS`): é o nome que
#: o laço do tique, a Mira e a troca de botões leem.
BOTAO_DA_ZONA_DE_BAIXO: Final = "l2_btn"
_SETORES_DO_DIRECIONAL: Final[tuple[frozenset[str], ...]] = (
    frozenset({"dpad_right"}),
    frozenset({"dpad_right", "dpad_up"}),
    frozenset({"dpad_up"}),
    frozenset({"dpad_up", "dpad_left"}),
    frozenset({"dpad_left"}),
    frozenset({"dpad_left", "dpad_down"}),
    frozenset({"dpad_down"}),
    frozenset({"dpad_down", "dpad_right"}),
)

_ATRIBUTO_DO_NEUTRO: Final = "_roteador_de_movimento_neutro"
_ATRIBUTO_DO_DEDO: Final = "_roteador_de_movimento_ultimo_dedo"


def _unitario(vetor: tuple[float, float, float]) -> tuple[float, float, float] | None:
    x, y, z = (float(v) for v in vetor)
    modulo = math.sqrt(x * x + y * y + z * z)
    if modulo < GRAVIDADE_MINIMA_G:
        return None
    return x / modulo, y / modulo, z / modulo


def inclinacao(
    acel: tuple[float, float, float], neutro: tuple[float, float, float]
) -> tuple[float, float] | None:
    """Quanto o controle inclinou desde o neutro, em graus: (direita, para trás).

    Pela GRAVIDADE que o acelerômetro lê (em g, `AccelSnapshot`). O horizontal
    é o volante: a elevação da gravidade no eixo `x` (o de lado a lado do
    controle) contra a do neutro. O vertical é a rotação em volta desse eixo,
    medida no plano `y`-`z` — sem supor qual dos dois aponta para cima, porque
    isso depende de como a pessoa segura. `None` sem gravidade legível.

    O SINAL É DA BANCADA, como o do giro (`_componentes`): a convenção de eixos
    é a da `hid-playstation` e da SDL (x para a direita, y saindo da face, z
    para quem segura), e quem corrige em dez segundos é o «Inverter».
    """
    a = _unitario(acel)
    n = _unitario(neutro)
    if a is None or n is None:
        return None
    direita = math.degrees(
        math.asin(max(-1.0, min(1.0, n[0]))) - math.asin(max(-1.0, min(1.0, a[0])))
    )
    para_tras = math.degrees(math.atan2(n[2] * a[1] - n[1] * a[2], n[1] * a[1] + n[2] * a[2]))
    return direita, para_tras


def deflexao_da_inclinacao(
    acel: tuple[float, float, float],
    neutro: tuple[float, float, float],
    arranjo: ArranjoDeMovimento,
) -> tuple[int, int]:
    """A inclinação desde o neutro vira deslocamento a SOMAR num analógico.

    `(dh, dv)` em unidades de eixo (-127..127), com a zona morta, o teto e a
    sensibilidade. Inclinar é POSIÇÃO, como o próprio analógico: a resposta é
    linear depois da zona morta (a curva do giro achata o começo, e aqui o
    começo é o que faz o personagem sair do lugar). O arranjo que não inclina
    devolve zero.
    """
    if not arranjo.inclina:
        return 0, 0
    angulos = inclinacao(acel, neutro)
    if angulos is None:
        return 0, 0
    horizontal, vertical = angulos
    if arranjo.inverter_horizontal:
        horizontal = -horizontal
    if arranjo.inverter_vertical:
        vertical = -vertical
    magnitude = math.hypot(horizontal, vertical)
    zona = ZONA_MORTA_DA_INCLINACAO_GRAUS
    if magnitude <= zona:
        return 0, 0
    teto = max(
        zona + 1.0,
        TETO_DA_INCLINACAO_GRAUS * SENSIBILIDADE_PADRAO / max(1, arranjo.sensibilidade),
    )
    alcance = min(1.0, (magnitude - zona) / (teto - zona)) * DEFLEXAO_MAXIMA
    return (
        round(alcance * horizontal / magnitude),
        round(alcance * vertical / magnitude),
    )


def neutro_da_inclinacao(
    dono: object,
    uniq: str,
    acel: tuple[float, float, float],
    agora: float,
) -> tuple[float, float, float]:
    """O NEUTRO desta peça: como ela estava na primeira leitura depois de um silêncio.

    Quem segura não segura na horizontal, e cada pessoa segura de um jeito: o
    neutro é o ângulo em que o controle estava quando a inclinação começou a
    valer — a rota ligada, o controle que voltou, o jogo que abriu. Um silêncio
    de :data:`SILENCIO_DA_DRENAGEM_S` sem leitura recomeça o neutro; e com o
    «Só enquanto eu segurar», o botão solto é silêncio, então cada aperto
    recentra. Sem `dono` (o `store` que não há) o neutro é a própria leitura, e
    a inclinação não move nada.

    O LIMITE, escrito (conferência de 28/09): o tique lê a peça a cada volta, e
    o controle parado na mesa não é silêncio. Se a rota ligou com ele deitado,
    a mesa é o neutro, e pegá-lo na mão anda até o próximo silêncio — o
    «Só enquanto eu segurar», o controle que volta, o chip apagado e aceso. É a
    prova da mão dela que decide se falta um gesto de recentrar.
    """
    if dono is None:
        return acel
    mapa = getattr(dono, _ATRIBUTO_DO_NEUTRO, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DO_NEUTRO, mapa)
    chave = chave_de_sensor(uniq)
    anterior = mapa.get(chave)
    if anterior is None or agora - anterior[1] > SILENCIO_DA_DRENAGEM_S:
        neutro = acel
    else:
        neutro = anterior[0]
    mapa[chave] = (neutro, agora)
    return neutro


def botoes_das_zonas(
    dedos: Iterable[tuple[float, float]], largura: int, altura: int
) -> frozenset[str]:
    """Os botões que os dedos apoiados apertam agora, na língua do leitor.

    `dedos` é uma sequência de `(x, y)` nas unidades do touchpad (o
    `TouchState.pontos`, até dois). Cada dedo aperta a zona em que está: dois
    dedos, duas zonas — o direcional e o L2 juntos, por exemplo. Sem dedo,
    nenhum botão: é o toque que aperta, e não o clique, porque apoiar o dedo
    custa menos que afundar a superfície (o clique pede força).
    """
    if largura <= 0 or altura <= 0:
        return frozenset()
    saida: set[str] = set()
    for x, y in dedos:
        fx = max(0.0, min(1.0, float(x) / largura))
        fy = max(0.0, min(1.0, float(y) / altura))
        if fx >= FRACAO_DO_DIRECIONAL:
            saida.add(BOTAO_DA_ZONA_DE_CIMA if fy < 0.5 else BOTAO_DA_ZONA_DE_BAIXO)
            continue
        dx = fx / FRACAO_DO_DIRECIONAL - 0.5
        dy = fy - 0.5
        if math.hypot(dx, dy) < MIOLO_DO_DIRECIONAL:
            continue
        angulo = math.degrees(math.atan2(-dy, dx)) % 360.0
        saida |= _SETORES_DO_DIRECIONAL[int(((angulo + 22.5) % 360.0) // 45.0)]
    return frozenset(saida)


def delta_do_toque(
    dono: object,
    uniq: str,
    dedos: Iterable[tuple[int, int, int]],
    agora: float,
) -> tuple[int, int]:
    """Quanto o dedo andou desde o tique anterior, nas unidades do touchpad.

    `dedos` é uma sequência de `(identidade, x, y)`. O cursor segue UM dedo — o
    mesmo do tique anterior, pela identidade do kernel —, e o dedo que chega,
    troca ou volta de um silêncio só ANCORA: levantar e reapoiar em outro ponto
    não salta o cursor, que é a regra do `TouchpadReader` do cursor da
    Navegação. Sem `dono`, nada anda.
    """
    if dono is None:
        return 0, 0
    mapa = getattr(dono, _ATRIBUTO_DO_DEDO, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DO_DEDO, mapa)
    chave = chave_de_sensor(uniq)
    anterior = mapa.get(chave)
    lista = list(dedos)
    if not lista:
        mapa.pop(chave, None)
        return 0, 0
    escolhido = lista[0]
    if anterior is not None:
        escolhido = next((d for d in lista if d[0] == anterior[0]), lista[0])
    identidade, x, y = escolhido
    mapa[chave] = (identidade, int(x), int(y), agora)
    if (
        anterior is None
        or anterior[0] != identidade
        or agora - anterior[3] > SILENCIO_DA_DRENAGEM_S
    ):
        return 0, 0
    return int(x) - anterior[1], int(y) - anterior[2]


def pixels_do_toque(dx: int, dy: int, arranjo: ArranjoDeMovimento) -> tuple[float, float]:
    """O dedo que andou vira pixels de cursor, pela `sensibilidade` do arranjo.

    Float de propósito, pela mesma razão de :func:`pixels`: quem trunca é quem
    emite, guardando o resto. Sem os «Inverter», que são do giro: o cursor
    segue o dedo, e um dedo que anda para a direita e leva o cursor para a
    esquerda não é ajuste, é defeito.
    """
    fator = PIXELS_POR_UNIDADE_DO_TOQUE * (arranjo.sensibilidade / SENSIBILIDADE_PADRAO)
    return dx * fator, dy * fator


def quer_cursor(dono: object) -> bool:
    """Alguma peça leva o touchpad ao cursor agora? É a pergunta do dono do nó."""
    mesa = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if type(mesa) is ArranjoDeMovimento and mesa.toque == TOQUE_CURSOR:
        return True
    return any(
        type(v) is ArranjoDeMovimento and v.toque == TOQUE_CURSOR
        for v in por_peca(dono).values()
    )


__all__ = [
    "BOTAO_DA_ZONA_DE_BAIXO",
    "BOTAO_DA_ZONA_DE_CIMA",
    "CAMPOS",
    "CENTRO_DO_EIXO",
    "DEFLEXAO_MAXIMA",
    "DESTINOS",
    "DESTINOS_DA_INCLINACAO",
    "DESTINO_ANALOGICO_DIREITO",
    "DESTINO_ANALOGICO_ESQUERDO",
    "DESTINO_MOUSE",
    "DESTINO_NENHUM",
    "EIXOS_HORIZONTAIS",
    "EIXO_ROLL",
    "EIXO_YAW",
    "EXPO_DO_GIRO",
    "FRACAO_DO_DIRECIONAL",
    "GRAVIDADE_MINIMA_G",
    "MIOLO_DO_DIRECIONAL",
    "PIXELS_POR_GRAU_PADRAO",
    "PIXELS_POR_UNIDADE_DO_TOQUE",
    "SENSIBILIDADE_MAX",
    "SENSIBILIDADE_MIN",
    "SENSIBILIDADE_PADRAO",
    "SILENCIO_DA_DRENAGEM_S",
    "SO_NAS_PECAS",
    "TETO_DA_INCLINACAO_GRAUS",
    "TETO_PADRAO_GRAUS_S",
    "TOQUES",
    "TOQUE_CURSOR",
    "TOQUE_ZONAS",
    "ZONA_MORTA_DA_INCLINACAO_GRAUS",
    "ZONA_MORTA_PADRAO_GRAUS_S",
    "ArranjoDeMovimento",
    "ArranjoRecusadoError",
    "angulo_do_tique",
    "arranjo_da_peca",
    "ativo",
    "botoes_das_zonas",
    "da_peca",
    "definir_ativo",
    "definir_da_peca",
    "definir_por_peca",
    "deflexao",
    "deflexao_da_inclinacao",
    "delta_do_toque",
    "inclinacao",
    "misturar",
    "montar",
    "neutro_da_inclinacao",
    "para_o_cursor",
    "parametros_da_peca",
    "pecas_que_miram",
    "pixels",
    "pixels_do_toque",
    "por_peca",
    "quer_cursor",
    "sincronizar_o_filtro",
]
