"""O roteador de movimento — o giroscópio vira algo que TODO jogo já lê.

MOVIMENTO-EM-QUALQUER-MASCARA-01 (21/09/2026), primeira entrega da camada 2 da
`ROTEADOR-DE-ENTRADA-01`. A tese é do usuário: *"universalizar todas as features do
dualsense independente do modo escolhido (…) a máscara é só pra enganar o
jogo"*.  <!-- noqa-acento: citação literal -->

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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from types import MappingProxyType
from typing import Final

from hefesto_dualsense4unix.core.virtual_motion import REGISTRO, chave_de_sensor

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
TOQUE_CURSOR: Final = "cursor"
TOQUE_ZONAS: Final = "zonas"
TOQUES: Final[tuple[str, ...]] = (DESTINO_NENHUM, TOQUE_CURSOR, TOQUE_ZONAS)
DESTINOS_DA_INCLINACAO: Final[tuple[str, ...]] = (
    DESTINO_NENHUM,
    DESTINO_ANALOGICO_ESQUERDO,
    DESTINO_ANALOGICO_DIREITO,
)
#: Os lados do Analógico Virtual: o giro e a inclinação movem o analógico deste lado.
LADOS_DO_VIRTUAL: Final[tuple[str, ...]] = (DESTINO_ANALOGICO_ESQUERDO, DESTINO_ANALOGICO_DIREITO)

EIXO_YAW: Final = "yaw"
EIXO_ROLL: Final = "roll"
EIXOS_HORIZONTAIS: Final[tuple[str, ...]] = (EIXO_YAW, EIXO_ROLL)

CENTRO_DO_EIXO: Final = 128
EIXO_MIN: Final = 0
EIXO_MAX: Final = 255
DEFLEXAO_MAXIMA: Final = 127

#: A ZONA MORTA, em graus/s. Um DualSense parado numa mesa não marca zero: o
ZONA_MORTA_PADRAO_GRAUS_S: Final = 3.0
TETO_PADRAO_GRAUS_S: Final = 220.0

SENSIBILIDADE_MIN: Final = 1
SENSIBILIDADE_MAX: Final = 12
SENSIBILIDADE_PADRAO: Final = 6

#: não importa `core/acoes_de_botao`.
EXPO_DO_GIRO: Final = 1.6

PIXELS_POR_GRAU_PADRAO: Final = 12.0

_ATRIBUTO_DO_ATIVO: Final = "_roteador_de_movimento_ativo"


class ArranjoRecusadoError(ValueError):
    """O arranjo declarado no perfil não faz sentido — com o motivo no texto."""


@dataclass(frozen=True, slots=True)
class ArranjoDeMovimento:
    """UM arranjo de mira por movimento — imutável, e é o que viaja pelo store."""

    destino: str = DESTINO_NENHUM
    sensibilidade: int = SENSIBILIDADE_PADRAO
    eixo_horizontal: str = EIXO_YAW
    inverter_horizontal: bool = False
    inverter_vertical: bool = False
    zona_morta_graus_s: float = ZONA_MORTA_PADRAO_GRAUS_S
    teto_graus_s: float = TETO_PADRAO_GRAUS_S
    pixels_por_grau: float = PIXELS_POR_GRAU_PADRAO
    gatilho: str | None = None
    toque: str = DESTINO_NENHUM
    acelerometro: str = DESTINO_NENHUM
    #: O «Mesmo parado» da Calibrar: a inclinação desta peça nunca pausa por parado.
    mesmo_parado: bool = False
    #: O lado guardado do Analógico Virtual: o `ligada` liga neste lado (no perfil antigo,
    #: o direito).
    lado: str = DESTINO_ANALOGICO_DIREITO

    @property
    def ligado(self) -> bool:
        """A MIRA (o giro) anda? `nenhum` é arranjo guardado e desligado."""
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
        """Alguma rota anda: o giro, o toque ou a inclinação."""
        return self.ligado or self.toca or self.inclina

    @property
    def quer_angulo(self) -> bool:
        """Este destino consome ÂNGULO percorrido (mouse) em vez de velocidade."""
        return self.destino == DESTINO_MOUSE


def _componentes(
    giro: tuple[float, float, float], arranjo: ArranjoDeMovimento
) -> tuple[float, float]:
    """Os três eixos do sensor viram (horizontal, vertical), já com o sinal."""
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
    """0.0 a 1.0: quanto do curso do eixo este movimento merece."""
    magnitude = math.hypot(horizontal, vertical)
    zona = max(0.0, arranjo.zona_morta_graus_s)
    if magnitude <= zona:
        return 0.0
    faixa = arranjo.teto_graus_s - zona
    if faixa <= 0.0:
        return 1.0
    return float(min(1.0, (magnitude - zona) / faixa) ** EXPO_DO_GIRO)


def deflexao(
    giro: tuple[float, float, float], arranjo: ArranjoDeMovimento
) -> tuple[int, int]:
    """Velocidade angular (graus/s) → deslocamento a SOMAR num analógico."""
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
    """Soma o giro ao analógico FÍSICO, com saturação."""
    return _saturar(eixo_h + dh), _saturar(eixo_v + dv)


def pixels(
    angulo: tuple[float, float, float], arranjo: ArranjoDeMovimento
) -> tuple[float, float]:
    """Ângulo percorrido (graus) → deslocamento de cursor, em pixels FLOAT."""
    if not arranjo.ligado:
        return 0.0, 0.0
    horizontal, vertical = _componentes(angulo, arranjo)
    fator = arranjo.pixels_por_grau * (arranjo.sensibilidade / SENSIBILIDADE_PADRAO)
    return horizontal * fator, vertical * fator


def montar(secao: object) -> ArranjoDeMovimento:
    """A seção do perfil vira arranjo SEMPRE — inclusive com o destino `nenhum`."""
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
    lado = str(getattr(secao, "lado", DESTINO_ANALOGICO_DIREITO) or DESTINO_ANALOGICO_DIREITO)
    if lado not in LADOS_DO_VIRTUAL:
        raise ArranjoRecusadoError(
            f"lado do analógico virtual desconhecido: {lado!r} "
            f"(conhecidos: {', '.join(LADOS_DO_VIRTUAL)})"
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
        mesmo_parado=bool(getattr(secao, "mesmo_parado", False)),
        lado=lado,
    )


def lado_do_virtual(arranjo: ArranjoDeMovimento) -> str:
    """O lado que a tela acende: o do giro; sem giro num analógico, o da inclinação; senão o
    guardado."""
    if arranjo.destino in LADOS_DO_VIRTUAL:
        return arranjo.destino
    if arranjo.acelerometro in LADOS_DO_VIRTUAL:
        return arranjo.acelerometro
    return arranjo.lado


def virtual_aceso(arranjo: ArranjoDeMovimento) -> bool:
    """O Analógico Virtual está aceso: o giro ou a inclinação move um analógico.

    O `mouse` não conta: o giro no cursor não é lado de analógico.
    """
    return arranjo.destino in LADOS_DO_VIRTUAL or arranjo.acelerometro in LADOS_DO_VIRTUAL


def definir_ativo(dono: object, arranjo: ArranjoDeMovimento | None) -> None:
    """Guarda o arranjo ATIVO no dono (o `StateStore`). `None` = sem mira."""
    if dono is None:
        return
    setattr(dono, _ATRIBUTO_DO_ATIVO, arranjo if arranjo is not None else None)


def ativo(dono: object) -> ArranjoDeMovimento | None:
    """O arranjo ativo, ou `None`. Custo de dois `getattr` no caminho do jogo."""
    valor = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if _roteia(valor):
        return valor
    if any(_roteia(v) for v in por_peca(dono).values()):
        return SO_NAS_PECAS
    return None


# migração: os campos são os mesmos"*. Entrou.  <!-- noqa-acento: citação literal -->

_ATRIBUTO_POR_PECA: Final = "_roteador_de_movimento_por_peca"

SO_NAS_PECAS: Final = ArranjoDeMovimento()

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
    """Os campos que a seção DIZ — só os escritos, quando ela sabe distinguir."""
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
    """O arranjo de UMA peça: a seção dela campo a campo por cima da do perfil."""
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
    """TROCA o mapa inteiro. `None` ou vazio = nenhuma peça tem opinião."""
    if dono is None:
        return
    limpo = {chave_de_sensor(k): v for k, v in (mapa or {}).items() if chave_de_sensor(k)}
    setattr(dono, _ATRIBUTO_POR_PECA, MappingProxyType(limpo))


def definir_da_peca(
    dono: object, uniq: str, arranjo: ArranjoDeMovimento | None, *, tem_opiniao: bool = True
) -> None:
    """Troca a opinião de UMA peça, e só dela — o gesto do chip, ao vivo."""
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
    """O arranjo que vale para a peça `uniq` AGORA, ou `None` (nenhuma rota)."""
    mapa = por_peca(dono)
    if mapa and uniq:
        chave = chave_de_sensor(uniq)
        if chave in mapa:
            valor = mapa[chave]
            return valor if _roteia(valor) else None
    return arranjo_da_mesa if _roteia(arranjo_da_mesa) else None  # type: ignore[return-value]


def parametros_da_peca(dono: object, uniq: str | None) -> ArranjoDeMovimento:
    """O arranjo desta peça MESMO DESLIGADO — o que os deslizantes mostram."""
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
    """Diz ao braço do REPORT quais peças estão mirando — o giro nativo sai delas."""
    if dono is None:
        return
    mesa = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    pecas = por_peca(dono)
    REGISTRO.definir_roteados(
        sem_chip=_ligado(mesa),
        por_peca={chave: _ligado(v) for chave, v in pecas.items()},
        toque_sem_chip=_toca(mesa),
        toque_por_peca={chave: _toca(v) for chave, v in pecas.items()},
    )


def para_o_cursor(arranjo: ArranjoDeMovimento) -> ArranjoDeMovimento:
    """O mesmo arranjo, com o cursor por destino — o que a Navegação faz com ele."""
    if not arranjo.ligado or arranjo.destino == DESTINO_MOUSE:
        return arranjo
    return replace(arranjo, destino=DESTINO_MOUSE)


def pecas_que_miram(dono: object) -> tuple[str, ...]:
    """As chaves das peças cuja OPINIÃO acende a mira — o chip de cada controle."""
    return tuple(chave for chave, valor in por_peca(dono).items() if _ligado(valor))


SILENCIO_DA_DRENAGEM_S: Final = 0.5

_ATRIBUTO_DA_DRENAGEM: Final = "_roteador_de_movimento_ultima_drenagem"


def angulo_do_tique(
    dono: object,
    uniq: str,
    angulo: tuple[float, float, float],
    agora: float,
) -> tuple[float, float, float] | None:
    """O ângulo que a peça acabou de drenar, ou `None` se ele é um acumulado."""
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


# há controle virtual — o modo DualSense e o modo Xbox, do P1 ao P4, no cabo e no

ZONA_MORTA_DA_INCLINACAO_GRAUS: Final = 6.0
TETO_DA_INCLINACAO_GRAUS: Final = 30.0
GRAVIDADE_MINIMA_G: Final = 0.2

PIXELS_POR_UNIDADE_DO_TOQUE: Final = 0.45

FRACAO_DO_DIRECIONAL: Final = 2.0 / 3.0
MIOLO_DO_DIRECIONAL: Final = 0.12
BOTAO_DA_ZONA_DE_CIMA: Final = "l1"
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
    """Quanto o controle inclinou desde o neutro, em graus: (direita, para trás)."""
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
    *,
    parada: bool = False,
) -> tuple[int, int]:
    """A inclinação desde o neutro vira deslocamento a SOMAR num analógico.

    `parada` (a peça que ninguém segura, `inclina_agora` falso) não inclina nada: o
    analógico volta ao centro, e o neutro da mão fica guardado na regra.
    """
    if not arranjo.inclina or parada:
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


# O CONTROLE PARADO NÃO INCLINA (D-2909-O-CONTROLE-PARADO-NAO-INCLINA, 29/09/2026):
# pelo pad virtual, o P2 largado na mesa segurava o esquerdo do jogo em X≈203, Y≈72,
# porque o neutro era o da mão e a mesa ficava 19° de lado e 14° de frente dele.
#: O maior pico a pico do giro, entre os três eixos, na janela. Não vê o viés: o ruído
#: de mesa de 21/09 andou 0,13 °/s acima da média, e o viés muda de controle para controle.
VARIACAO_DO_PARADO_GRAUS_S: Final = 1.5
#: O quanto a gravidade pode andar na janela: protege a inclinação lenta e lisa, que tem
#: pico a pico zero no giro (a 0,7 °/s ela já anda mais que isto em 3 s).
GRAVIDADE_DO_PARADO_GRAUS: Final = 2.0
#: A janela quieta de 21/09 (60 amostras a 20 Hz).
TEMPO_DO_PARADO_S: Final = 3.0
#: A gravidade que anda isto desde o parado tira do parado. Pico de giro sozinho não tira:
#: a batida na mesa, o botão no controle deitado e a vibração não mexem a gravidade.
SAIDA_DO_PARADO_GRAUS: Final = 3.0
#: O neutro que nasceu na mesa se reaprende quando a mão assenta: o giro (norma) abaixo
#: disto por `TEMPO_DO_ASSENTO_S`, com a gravidade andando menos que `SAIDA_DO_PARADO_GRAUS`.
LIMIAR_DO_ASSENTO_GRAUS_S: Final = 20.0
TEMPO_DO_ASSENTO_S: Final = 0.5


@dataclass(slots=True)
class _Repouso:
    """O que a regra lembra de UMA peça entre dois tiques."""

    neutro: tuple[float, float, float]
    carimbo: float
    inicio: float
    menor: list[float]
    maior: list[float]
    gravidade_do_inicio: tuple[float, float, float]
    virgem: bool = True
    parado: bool = False
    gravidade_do_parado: tuple[float, float, float] | None = None
    provisorio: bool = False
    assentando: bool = False
    assento_desde: float = 0.0
    gravidade_do_assento: tuple[float, float, float] | None = None


def _graus_entre(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """O ângulo entre duas leituras do acelerômetro; sem gravidade, 0."""
    ua, ub = _unitario(a), _unitario(b)
    if ua is None or ub is None:
        return 0.0
    produto = ua[0] * ub[0] + ua[1] * ub[1] + ua[2] * ub[2]
    return math.degrees(math.acos(max(-1.0, min(1.0, produto))))


def _recomecar_a_janela(
    estado: _Repouso, giro: tuple[float, float, float], acel: tuple[float, float, float],
    agora: float,
) -> None:
    estado.inicio = agora
    estado.menor = [float(v) for v in giro]
    estado.maior = [float(v) for v in giro]
    estado.gravidade_do_inicio = acel


def _o_tique_da_janela(
    estado: _Repouso, giro: tuple[float, float, float], acel: tuple[float, float, float],
    agora: float,
) -> None:
    """A janela quieta anda um tique; ao fechar 3 s, a peça está parada."""
    for eixo, valor in enumerate(giro):
        estado.menor[eixo] = min(estado.menor[eixo], float(valor))
        estado.maior[eixo] = max(estado.maior[eixo], float(valor))
    variacao = max(m - n for m, n in zip(estado.maior, estado.menor, strict=True))
    if (
        variacao > VARIACAO_DO_PARADO_GRAUS_S
        or _graus_entre(acel, estado.gravidade_do_inicio) > GRAVIDADE_DO_PARADO_GRAUS
    ):
        _recomecar_a_janela(estado, giro, acel, agora)
        estado.virgem = False
        return
    if agora - estado.inicio > TEMPO_DO_PARADO_S:
        estado.parado = True
        estado.gravidade_do_parado = acel
        estado.provisorio = estado.provisorio or estado.virgem
        estado.assentando = False


def _o_tique_do_assento(
    estado: _Repouso, giro: tuple[float, float, float], acel: tuple[float, float, float],
    agora: float,
) -> None:
    """O neutro provisório espera a mão assentar, e ali vira a leitura dela."""
    calmo = math.sqrt(sum(float(v) * float(v) for v in giro)) < LIMIAR_DO_ASSENTO_GRAUS_S
    base = estado.gravidade_do_assento
    if not calmo or base is None or _graus_entre(acel, base) >= SAIDA_DO_PARADO_GRAUS:
        estado.assento_desde = agora
        estado.gravidade_do_assento = acel
        return
    if agora - estado.assento_desde >= TEMPO_DO_ASSENTO_S:
        estado.neutro = acel
        estado.provisorio = False
        estado.assentando = False


def neutro_da_inclinacao(
    dono: object,
    uniq: str,
    acel: tuple[float, float, float],
    agora: float,
    giro: tuple[float, float, float] | None = None,
    *,
    mesmo_parado: bool = False,
) -> tuple[float, float, float]:
    """O NEUTRO desta peça: como ela estava na primeira leitura depois de um silêncio.

    Com o `giro` (a velocidade angular do mesmo tique), a regra também sabe se a peça
    está PARADA: o giro variando menos de `VARIACAO_DO_PARADO_GRAUS_S` de pico a pico
    em cada eixo e a gravidade andando menos de `GRAVIDADE_DO_PARADO_GRAUS`, por
    `TEMPO_DO_PARADO_S`. Parada, a inclinação dela sai do analógico
    (`inclina_agora` responde falso) e o neutro da mão fica guardado: não se recentra
    na mesa, porque pegar de volta andaria sozinho. Sai do parado quando a gravidade
    anda `SAIDA_DO_PARADO_GRAUS`, e a inclinação volta na hora contra o neutro antigo.
    O neutro que NASCEU com a peça quieta é provisório e se reaprende quando a mão
    assenta. `mesmo_parado` (o «Mesmo parado» da Calibrar) nunca entra no parado.
    `giro=None` é o comportamento de antes, byte a byte: sem leitura ninguém para.
    """
    if dono is None:
        return acel
    mapa = getattr(dono, _ATRIBUTO_DO_NEUTRO, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DO_NEUTRO, mapa)
    chave = chave_de_sensor(uniq)
    estado = mapa.get(chave)
    zero = (0.0, 0.0, 0.0) if giro is None else giro
    if not isinstance(estado, _Repouso) or agora - estado.carimbo > SILENCIO_DA_DRENAGEM_S:
        estado = _Repouso(
            neutro=acel, carimbo=agora, inicio=agora,
            menor=[float(v) for v in zero], maior=[float(v) for v in zero],
            gravidade_do_inicio=acel,
        )
        mapa[chave] = estado
    else:
        estado.carimbo = agora
    if giro is None or mesmo_parado:
        estado.parado = estado.assentando = estado.provisorio = False
        _recomecar_a_janela(estado, zero, acel, agora)
        estado.virgem = False
        return estado.neutro
    if estado.parado:
        base = estado.gravidade_do_parado
        if base is None or _graus_entre(acel, base) < SAIDA_DO_PARADO_GRAUS:
            return estado.neutro
        estado.parado = False
        estado.virgem = False
        _recomecar_a_janela(estado, giro, acel, agora)
        if estado.provisorio:
            estado.assentando = True
            estado.assento_desde = agora
            estado.gravidade_do_assento = acel
        return estado.neutro
    if estado.assentando:
        _o_tique_do_assento(estado, giro, acel, agora)
    _o_tique_da_janela(estado, giro, acel, agora)
    return estado.neutro


def inclina_agora(dono: object, uniq: str) -> bool:
    """A inclinação desta peça vai ao analógico: nem parada, nem esperando a mão assentar."""
    mapa = getattr(dono, _ATRIBUTO_DO_NEUTRO, None)
    estado = mapa.get(chave_de_sensor(uniq)) if isinstance(mapa, dict) else None
    if not isinstance(estado, _Repouso):
        return True
    return not (estado.parado or estado.assentando)


def inclinacao_parada(dono: object, uniq: str, agora: float) -> bool:
    """A última resposta da regra para esta peça: parada agora (o chip meio apagado).

    Sem tique há mais de `SILENCIO_DA_DRENAGEM_S` (a rota apagou, o controle saiu),
    a resposta é falsa: a regra não mede o que não lê.
    """
    mapa = getattr(dono, _ATRIBUTO_DO_NEUTRO, None)
    estado = mapa.get(chave_de_sensor(uniq)) if isinstance(mapa, dict) else None
    if not isinstance(estado, _Repouso) or agora - estado.carimbo > SILENCIO_DA_DRENAGEM_S:
        return False
    return estado.parado


def botoes_das_zonas(
    dedos: Iterable[tuple[float, float]], largura: int, altura: int
) -> frozenset[str]:
    """Os botões que os dedos apoiados apertam agora, na língua do leitor."""
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
    """Quanto o dedo andou desde o tique anterior, nas unidades do touchpad."""
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
    """O dedo que andou vira pixels de cursor, pela `sensibilidade` do arranjo."""
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


# O ZERO DE CADA CONTROLE (O-COMECAR-DA-CALIBRAR-GUARDA-O-ZERO-DE-CADA-CONTROLE-01, 08/10/2026):
# um DualSense parado na mesa não marca zero no giro, e com a zona morta baixa a Mira anda
# sozinha. O «Começar» da Calibrar mede o repouso de cada controle por `SEGUNDOS_DO_ZERO`,
# com a mesma régua do parado (`_o_tique_da_janela`, sem segunda medida), e o viés medido
# sai do giro antes da Mira e da inclinação. A chave é a de sensor: o endereço, o mesmo no
# cabo e no BT. Nada se escreve no controle; o disco é do `utils/session.py`.

#: Os 5 s que a Calibrar diz na tela (`interface/calibrar.SEGUNDOS`).
SEGUNDOS_DO_ZERO: Final = 5.0
#: Menos que isto não é medida: a janela de 5 s a 50 Hz dá 250.
MINIMO_DE_AMOSTRAS_DO_ZERO: Final = 20

_ATRIBUTO_DO_ZERO: Final = "_roteador_de_movimento_zero"

Vetor = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ZeroDoControle:
    """O repouso medido de UM controle: o viés do giro (°/s) e a gravidade (g)."""

    giro: Vetor
    gravidade: Vetor


def _media(vetores: Sequence[Vetor]) -> Vetor:
    n = float(len(vetores))
    return (
        sum(float(v[0]) for v in vetores) / n,
        sum(float(v[1]) for v in vetores) / n,
        sum(float(v[2]) for v in vetores) / n,
    )


def medir_o_zero(amostras: Sequence[tuple[Vetor, Vetor]]) -> ZeroDoControle | None:
    """O zero de uma peça a partir das amostras `(giro, acel)` da medida; `None` se mexeu.

    A régua é a do parado: a janela quieta que recomeça quando o giro varia mais de
    `VARIACAO_DO_PARADO_GRAUS_S` de pico a pico ou a gravidade anda mais de
    `GRAVIDADE_DO_PARADO_GRAUS`. Recomeçou uma vez, a peça mexeu e nada se guarda.
    """
    lista = list(amostras)
    if len(lista) < MINIMO_DE_AMOSTRAS_DO_ZERO:
        return None
    giro0, acel0 = lista[0]
    estado = _Repouso(
        neutro=acel0, carimbo=0.0, inicio=0.0,
        menor=[float(v) for v in giro0], maior=[float(v) for v in giro0],
        gravidade_do_inicio=acel0,
    )
    for giro, acel in lista[1:]:
        _o_tique_da_janela(estado, giro, acel, 0.0)
        if not estado.virgem:
            return None
    return ZeroDoControle(
        giro=_media([g for g, _ in lista]), gravidade=_media([a for _, a in lista])
    )


def _zeros(dono: object) -> dict[str, ZeroDoControle]:
    mapa = getattr(dono, _ATRIBUTO_DO_ZERO, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DO_ZERO, mapa)
    return mapa


def definir_o_zero(dono: object, uniq: str, zero: ZeroDoControle | None) -> None:
    """Guarda (ou, com `None`, esquece) o zero de UM controle."""
    if dono is None:
        return
    chave = chave_de_sensor(uniq)
    if not chave:
        return
    mapa = _zeros(dono)
    if zero is None:
        mapa.pop(chave, None)
    else:
        mapa[chave] = zero


def zero_de(dono: object, uniq: str | None) -> ZeroDoControle | None:
    """O zero guardado deste controle, ou `None`."""
    if dono is None or not uniq:
        return None
    mapa = getattr(dono, _ATRIBUTO_DO_ZERO, None)
    if not isinstance(mapa, dict):
        return None
    zero = mapa.get(chave_de_sensor(uniq))
    return zero if isinstance(zero, ZeroDoControle) else None


def descontar_o_vies(dono: object, uniq: str | None, giro: Vetor | None) -> Vetor | None:
    """O giro desta peça sem o viés medido; sem zero guardado, o MESMO objeto."""
    if giro is None:
        return None
    zero = zero_de(dono, uniq)
    if zero is None:
        return giro
    vies = zero.giro
    return (
        float(giro[0]) - vies[0],
        float(giro[1]) - vies[1],
        float(giro[2]) - vies[2],
    )


def zeros_para_gravar(dono: object) -> dict[str, dict[str, list[float]]]:
    """Os zeros guardados, na forma do arquivo: chave de sensor → giro e gravidade."""
    mapa = getattr(dono, _ATRIBUTO_DO_ZERO, None)
    if not isinstance(mapa, dict):
        return {}
    return {
        chave: {"giro": list(zero.giro), "gravidade": list(zero.gravidade)}
        for chave, zero in sorted(mapa.items())
        if isinstance(zero, ZeroDoControle)
    }


def _vetor(valor: object) -> Vetor | None:
    if not isinstance(valor, (list, tuple)) or len(valor) != 3:
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valor):
        return None
    x, y, z = (float(v) for v in valor)
    if not all(math.isfinite(v) for v in (x, y, z)):
        return None
    return (x, y, z)


def carregar_os_zeros(dono: object, dados: object) -> int:
    """Devolve ao `dono` os zeros lidos do arquivo; a entrada torta fica de fora."""
    if dono is None or not isinstance(dados, Mapping):
        return 0
    contados = 0
    for chave, valor in dados.items():
        if not isinstance(valor, Mapping):
            continue
        giro, gravidade = _vetor(valor.get("giro")), _vetor(valor.get("gravidade"))
        if giro is None or gravidade is None or not chave_de_sensor(str(chave)):
            continue
        definir_o_zero(dono, str(chave), ZeroDoControle(giro=giro, gravidade=gravidade))
        contados += 1
    return contados


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
    "GRAVIDADE_DO_PARADO_GRAUS",
    "GRAVIDADE_MINIMA_G",
    "LIMIAR_DO_ASSENTO_GRAUS_S",
    "MINIMO_DE_AMOSTRAS_DO_ZERO",
    "MIOLO_DO_DIRECIONAL",
    "PIXELS_POR_GRAU_PADRAO",
    "PIXELS_POR_UNIDADE_DO_TOQUE",
    "SAIDA_DO_PARADO_GRAUS",
    "SEGUNDOS_DO_ZERO",
    "SENSIBILIDADE_MAX",
    "SENSIBILIDADE_MIN",
    "SENSIBILIDADE_PADRAO",
    "SILENCIO_DA_DRENAGEM_S",
    "SO_NAS_PECAS",
    "TEMPO_DO_ASSENTO_S",
    "TEMPO_DO_PARADO_S",
    "TETO_DA_INCLINACAO_GRAUS",
    "TETO_PADRAO_GRAUS_S",
    "TOQUES",
    "TOQUE_CURSOR",
    "TOQUE_ZONAS",
    "VARIACAO_DO_PARADO_GRAUS_S",
    "ZONA_MORTA_DA_INCLINACAO_GRAUS",
    "ZONA_MORTA_PADRAO_GRAUS_S",
    "ArranjoDeMovimento",
    "ArranjoRecusadoError",
    "ZeroDoControle",
    "angulo_do_tique",
    "arranjo_da_peca",
    "ativo",
    "botoes_das_zonas",
    "carregar_os_zeros",
    "da_peca",
    "definir_ativo",
    "definir_da_peca",
    "definir_o_zero",
    "definir_por_peca",
    "deflexao",
    "deflexao_da_inclinacao",
    "delta_do_toque",
    "descontar_o_vies",
    "inclina_agora",
    "inclinacao",
    "inclinacao_parada",
    "medir_o_zero",
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
    "zero_de",
    "zeros_para_gravar",
]
