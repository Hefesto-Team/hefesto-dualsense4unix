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
from dataclasses import dataclass
from typing import Final

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

    @property
    def ligado(self) -> bool:
        """Há alguma coisa a fazer? `nenhum` é arranjo guardado e desligado."""
        return self.destino != DESTINO_NENHUM and self.destino in DESTINOS

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
    """
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
    horizontal, vertical = _componentes(angulo, arranjo)
    fator = arranjo.pixels_por_grau * (arranjo.sensibilidade / SENSIBILIDADE_PADRAO)
    return horizontal * fator, vertical * fator


def resolver(secao: object) -> ArranjoDeMovimento | None:
    """A seção do perfil vira arranjo — ou `None`, que é *"sem opinião"*.

    `None` e o destino `nenhum` viram os dois `None`: o tique não paga nem um
    `getattr` a mais no caso normal, que é o caso de quase todo perfil.

    LEVANTA `ArranjoRecusadoError` no que o esquema deixaria passar mas o motor
    não sabe fazer — destino desconhecido, eixo desconhecido, teto abaixo da
    zona morta. Quem chama (`ProfileManager.apply_movimento`) trata a recusa
    desligando só esta seção: as luzes e os gatilhos dela não pagam por uma
    linha torta, que é o contrato do `apply_remapeamento`.
    """
    if secao is None:
        return None
    destino = str(getattr(secao, "destino", DESTINO_NENHUM) or DESTINO_NENHUM)
    if destino == DESTINO_NENHUM:
        return None
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
    """O arranjo ativo, ou `None`. Custo de um `getattr` no caminho do jogo.

    SÓ UM `ArranjoDeMovimento` DE VERDADE VALE: um dublê feito de `MagicMock`
    responde qualquer atributo com outro mock, e um mock no caminho do jogo
    somaria um `Mock` a um inteiro e derrubaria o tique inteiro do controle. A
    checagem de tipo é a mesma trava do `remapeamento_de_botao.ativo`, e pelo
    mesmo susto.
    """
    valor = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if type(valor) is not ArranjoDeMovimento:
        return None
    return valor if valor.ligado else None


__all__ = [
    "CENTRO_DO_EIXO",
    "DEFLEXAO_MAXIMA",
    "DESTINOS",
    "DESTINO_ANALOGICO_DIREITO",
    "DESTINO_ANALOGICO_ESQUERDO",
    "DESTINO_MOUSE",
    "DESTINO_NENHUM",
    "EIXOS_HORIZONTAIS",
    "EIXO_ROLL",
    "EIXO_YAW",
    "EXPO_DO_GIRO",
    "PIXELS_POR_GRAU_PADRAO",
    "SENSIBILIDADE_MAX",
    "SENSIBILIDADE_MIN",
    "SENSIBILIDADE_PADRAO",
    "TETO_PADRAO_GRAUS_S",
    "ZONA_MORTA_PADRAO_GRAUS_S",
    "ArranjoDeMovimento",
    "ArranjoRecusadoError",
    "ativo",
    "definir_ativo",
    "deflexao",
    "misturar",
    "pixels",
    "resolver",
]
