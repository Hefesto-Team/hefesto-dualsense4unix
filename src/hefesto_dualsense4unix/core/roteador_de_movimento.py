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
from collections.abc import Mapping
from dataclasses import dataclass, fields
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
    """O arranjo ativo, ou `None`. Custo de dois `getattr` no caminho do jogo.

    SÓ UM `ArranjoDeMovimento` DE VERDADE VALE: um dublê feito de `MagicMock`
    responde qualquer atributo com outro mock, e um mock no caminho do jogo
    somaria um `Mock` a um inteiro e derrubaria o tique inteiro do controle. A
    checagem de tipo é a mesma trava do `remapeamento_de_botao.ativo`, e pelo
    mesmo susto.
    """
    valor = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if type(valor) is ArranjoDeMovimento and valor.ligado:
        return valor
    # A MESA EM QUE SÓ ALGUNS CONTROLES MIRAM — A-MIRA-POR-MOVIMENTO-NA-TELA-01.
    # Os dois laços do tique (`gamepad.dispatch_gamepad` e
    # `coop.CoopManager.forward_all`) só chamam o motor quando esta função
    # devolve alguma coisa. Sem mira no perfil e com o chip «Mira Virtual»
    # aceso no P3, um `None` aqui calaria o P3 junto com a mesa. Quem decide
    # QUAL peça mira é o `da_peca`, chamado pelo motor com o `uniq` na mão.
    if any(_ligado(v) for v in por_peca(dono).values()):
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
    """Só um `ArranjoDeMovimento` de verdade, e ligado — a trava do `ativo()`."""
    return type(valor) is ArranjoDeMovimento and valor.ligado


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
    """O arranjo que vale para a peça `uniq` AGORA, ou `None` (ela não mira).

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
            return valor if _ligado(valor) else None
    return arranjo_da_mesa if _ligado(arranjo_da_mesa) else None  # type: ignore[return-value]


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
    REGISTRO.definir_roteados(
        padrao=_ligado(mesa),
        por_peca={chave: _ligado(v) for chave, v in por_peca(dono).items()},
    )


__all__ = [
    "CAMPOS",
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
    "SO_NAS_PECAS",
    "TETO_PADRAO_GRAUS_S",
    "ZONA_MORTA_PADRAO_GRAUS_S",
    "ArranjoDeMovimento",
    "ArranjoRecusadoError",
    "arranjo_da_peca",
    "ativo",
    "da_peca",
    "definir_ativo",
    "definir_da_peca",
    "definir_por_peca",
    "deflexao",
    "misturar",
    "montar",
    "parametros_da_peca",
    "pixels",
    "por_peca",
    "sincronizar_o_filtro",
]
