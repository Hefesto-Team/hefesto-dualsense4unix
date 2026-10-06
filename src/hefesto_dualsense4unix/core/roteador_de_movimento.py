"""O roteador de movimento — o giroscópio vira algo que TODO jogo já lê.

MOVIMENTO-EM-QUALQUER-MASCARA-01 (21/09/2026), primeira entrega da camada 2 da
`ROTEADOR-DE-ENTRADA-01`. A tese é dela: *"universalizar todas as features do
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
from collections.abc import Iterable, Mapping
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
) -> tuple[int, int]:
    """A inclinação desde o neutro vira deslocamento a SOMAR num analógico."""
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
    """O NEUTRO desta peça: como ela estava na primeira leitura depois de um silêncio."""
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
