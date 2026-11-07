"""O roteador de movimento — o giroscópio vira algo que TODO jogo já lê.

MOVIMENTO-EM-QUALQUER-MASCARA-01 (21/09/2026), primeira entrega da camada 2 da
`ROTEADOR-DE-ENTRADA-01`. A tese: toda feature do DualSense vale em qualquer
modo escolhido, e a máscara só serve para o jogo reconhecer o controle,
sem tirar nada do que o aparelho faz.

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
import struct
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from types import MappingProxyType, SimpleNamespace
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
LADOS_DO_VIRTUAL: Final[tuple[str, ...]] = (DESTINO_ANALOGICO_ESQUERDO, DESTINO_ANALOGICO_DIREITO)

CENTRO_DO_EIXO: Final = 128
EIXO_MIN: Final = 0
EIXO_MAX: Final = 255
DEFLEXAO_MAXIMA: Final = 127

ZONA_MORTA_PADRAO_GRAUS_S: Final = 3.0
RUIDO_DO_GIRO_GRAUS_S: Final = 1.0

SENSIBILIDADE_MIN: Final = 0
SENSIBILIDADE_MAX: Final = 10
SENSIBILIDADE_PADRAO: Final = 4

VELOCIDADE_DO_JOGO_PADRAO_GRAUS_S: Final = 180.0
PISO_PADRAO: Final = 0.27
GANHO_NA_SENSIBILIDADE_PADRAO: Final = 1.5

MENOR_PLANO_DA_GRAVIDADE: Final = 0.5
GRAVIDADE_DE_BASE: Final[tuple[float, float, float]] = (0.0, 1.0, 0.0)
TEMPO_DA_GRAVIDADE_S: Final = 0.25

PIXELS_POR_GRAU_PADRAO: Final = 12.0

_ATRIBUTO_DO_ATIVO: Final = "_roteador_de_movimento_ativo"


class ArranjoRecusadoError(ValueError):
    """O arranjo declarado no perfil não faz sentido — com o motivo no texto."""


@dataclass(frozen=True, slots=True)
class ArranjoDeMovimento:
    """UM arranjo de mira por movimento — imutável, e é o que viaja pelo store."""

    destino: str = DESTINO_NENHUM
    sensibilidade_h: int = SENSIBILIDADE_PADRAO
    sensibilidade_v: int = SENSIBILIDADE_PADRAO
    inverter_horizontal: bool = False
    inverter_vertical: bool = False
    zona_morta_graus_s: float = ZONA_MORTA_PADRAO_GRAUS_S
    velocidade_do_jogo: float = VELOCIDADE_DO_JOGO_PADRAO_GRAUS_S
    piso: float = PISO_PADRAO
    pixels_por_grau: float = PIXELS_POR_GRAU_PADRAO
    gatilho: str | None = None
    toque: str = DESTINO_NENHUM
    mesmo_parado: bool = False
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
    def roteia(self) -> bool:
        """Alguma rota anda: o giro ou o toque."""
        return self.ligado or self.toca

    @property
    def quer_angulo(self) -> bool:
        """Este destino consome ÂNGULO percorrido (mouse) em vez de velocidade."""
        return self.destino == DESTINO_MOUSE


def _no_espaco_do_jogador(
    vetor: tuple[float, float, float], gravidade: tuple[float, float, float] | None
) -> tuple[float, float]:
    """(para a esquerda, para cima): o giro do controle no espaço de quem o segura.

    O horizontal soma, no plano y e z, as duas formas de virar: em torno da vertical do mundo e
    como volante, em torno do eixo que aponta para quem segura. Valem em qualquer altura da mão,
    e a soma para em `hypot(gy, gz)` para o gesto entre as duas não valer em dobro. Medido em
    06/11, no cabo e no rádio: esquerda dá `ABS_RY` positivo, nariz para cima dá `ABS_RX` positivo.
    """
    gx, gy, gz = vetor
    _ux, uy, uz = GRAVIDADE_DE_BASE if gravidade is None else gravidade
    plano = max(MENOR_PLANO_DA_GRAVIDADE, math.hypot(uy, uz))
    cima_y, cima_z = uy / plano, uz / plano
    em_torno_da_vertical = gy * cima_y + gz * cima_z
    como_volante = gz * cima_y - gy * cima_z
    soma = em_torno_da_vertical + como_volante
    return math.copysign(min(abs(soma), math.hypot(gy, gz)), soma), gx


def _componentes(
    giro: tuple[float, float, float],
    arranjo: ArranjoDeMovimento,
    gravidade: tuple[float, float, float] | None = None,
) -> tuple[float, float]:
    """Os três eixos do sensor viram (direita, baixo) do analógico, já com o sinal."""
    esquerda, cima = _no_espaco_do_jogador(giro, gravidade)
    horizontal = -esquerda
    vertical = -cima
    if arranjo.inverter_horizontal:
        horizontal = -horizontal
    if arranjo.inverter_vertical:
        vertical = -vertical
    return horizontal, vertical


def _acima_da_zona(magnitude: float, arranjo: ArranjoDeMovimento) -> bool:
    """A regra da zona morta, num lugar só: a velocidade passa do «Ignorar tremor até»."""
    return magnitude > max(0.0, arranjo.zona_morta_graus_s)


def passa_da_zona_morta(
    giro: tuple[float, float, float],
    arranjo: ArranjoDeMovimento,
    gravidade: tuple[float, float, float] | None = None,
) -> bool:
    """O giro (graus/s) passa da zona morta, sem o arredondamento do eixo do analógico.

    É o portão do cursor: o eixo do analógico tem 256 passos, o cursor carrega o resto
    sub-pixel, e a quantização de um não decide o outro.
    """
    if not arranjo.ligado:
        return False
    horizontal, vertical = _componentes(giro, arranjo, gravidade)
    return _acima_da_zona(math.hypot(horizontal, vertical), arranjo)


def _saida_do_eixo(
    velocidade: float, sensibilidade: int, arranjo: ArranjoDeMovimento, ganho: float
) -> float:
    """UM eixo do analógico, em contagens exatas: o inverso da resposta do analógico do jogo.

    `piso` é onde o jogo começa a ler o analógico, e o resto do curso pede ao jogo a velocidade
    que a mão fez. O ganho da Imersão pesa acima do piso, para nunca calar a mira. Com a zona em
    zero, o ruído do sensor (`RUIDO_DO_GIRO_GRAUS_S`) não acende o piso.
    """
    magnitude = abs(velocidade)
    zona = max(RUIDO_DO_GIRO_GRAUS_S, arranjo.zona_morta_graus_s)
    if sensibilidade <= 0 or magnitude <= zona:
        return 0.0
    piso = max(0.0, min(1.0, arranjo.piso))
    ganho_do_eixo = GANHO_NA_SENSIBILIDADE_PADRAO * sensibilidade / SENSIBILIDADE_PADRAO * ganho
    curso = min(1.0, ganho_do_eixo * (magnitude - zona) / arranjo.velocidade_do_jogo)
    return math.copysign((piso + (1.0 - piso) * curso) * DEFLEXAO_MAXIMA, velocidade)


def _deflexao_exata(
    giro: tuple[float, float, float],
    arranjo: ArranjoDeMovimento,
    ganho: float,
    gravidade: tuple[float, float, float] | None,
) -> tuple[float, float]:
    if not arranjo.ligado:
        return 0.0, 0.0
    horizontal, vertical = _componentes(giro, arranjo, gravidade)
    return (
        _saida_do_eixo(horizontal, arranjo.sensibilidade_h, arranjo, ganho),
        _saida_do_eixo(vertical, arranjo.sensibilidade_v, arranjo, ganho),
    )


GANHO_MINIMO_DA_MIRA: Final = 0.3
PRAZO_MAXIMO_DO_PESO_MS: Final = 10_000
TODOS_OS_CONTROLES: Final = "todos"


class PesoDaMira:
    """O ganho que uma extensão pede para o giro, por controle ou para ``todos``, com prazo.

    Sem pedido vivo o ganho é 1; com mais de um, vale o menor. O pedido some no prazo e quando
    quem o fez é solto; quem ouve :meth:`ao_esvaziar` é avisado quando o último some.
    """

    def __init__(self, relogio: Callable[[], float] = time.monotonic) -> None:
        self.relogio = relogio
        self._trava = threading.Lock()
        self._pedidos: dict[tuple[str, str], tuple[float, float]] = {}
        self._avisos: list[Callable[[], None]] = []

    def pedir(self, dono: str, alvo: str, ganho: float, ate_ms: int) -> None:
        if not GANHO_MINIMO_DA_MIRA <= ganho <= 1.0:
            raise ValueError(f"o ganho vai de {GANHO_MINIMO_DA_MIRA} a 1")
        if not 0 < ate_ms <= PRAZO_MAXIMO_DO_PESO_MS:
            raise ValueError(f"o prazo vai de 1 a {PRAZO_MAXIMO_DO_PESO_MS} ms")
        chave = alvo if alvo == TODOS_OS_CONTROLES else chave_de_sensor(alvo)
        with self._trava:
            self._pedidos[(dono, chave)] = (ganho, self.relogio() + ate_ms / 1000.0)

    def ganho(self, uniq: str | None) -> float:
        if not self._pedidos:
            return 1.0
        agora = self.relogio()
        chave = chave_de_sensor(uniq) if uniq else None
        menor = 1.0
        with self._trava:
            havia = bool(self._pedidos)
            for par, (ganho, ate) in list(self._pedidos.items()):
                if ate <= agora:
                    del self._pedidos[par]
                elif par[1] in (TODOS_OS_CONTROLES, chave):
                    menor = min(menor, ganho)
        self._avisar_se_esvaziou(havia)
        return menor

    def vencer(self) -> None:
        """Tira os pedidos cujo prazo passou, sem esperar a leitura do giro."""
        self.ganho(None)

    def ultimo_prazo(self) -> float | None:
        """O instante, no ``relogio``, em que o último pedido vivo vence; ``None`` sem pedido."""
        with self._trava:
            return max((ate for _ganho, ate in self._pedidos.values()), default=None)

    def ao_esvaziar(self, aviso: Callable[[], None]) -> Callable[[], None]:
        """Chama ``aviso`` cada vez que o último pedido some; devolve quem o desliga."""
        with self._trava:
            self._avisos.append(aviso)

        def esquecer() -> None:
            with self._trava:
                if aviso in self._avisos:
                    self._avisos.remove(aviso)

        return esquecer

    def _avisar_se_esvaziou(self, havia: bool) -> None:
        with self._trava:
            avisos = list(self._avisos) if havia and not self._pedidos else []
        for aviso in avisos:
            aviso()

    def soltar(self, dono: str | None = None, uniq: str | None = None) -> None:
        """Solta os pedidos de ``dono`` (de todos, sem ``dono``), só os de ``uniq`` quando dito."""
        chave = chave_de_sensor(uniq) if uniq else None
        with self._trava:
            havia = bool(self._pedidos)
            for par in list(self._pedidos):
                if dono is not None and par[0] != dono:
                    continue
                if chave is not None and par[1] not in (chave, TODOS_OS_CONTROLES):
                    continue
                del self._pedidos[par]
        self._avisar_se_esvaziou(havia)

    def donos(self) -> frozenset[str]:
        with self._trava:
            return frozenset(dono for dono, _alvo in self._pedidos)


PESO_DA_MIRA = PesoDaMira()


_GIRO = struct.Struct("<3h")


def pesar_a_janela(janela: bytes, ganho: float) -> bytes:
    """Os três eixos do giro da janela vezes ``ganho``; com ganho 1, a mesma janela, byte a byte."""
    if ganho >= 1.0 or len(janela) < _GIRO.size:
        return janela
    eixos = (max(-32768, min(32767, round(v * ganho))) for v in _GIRO.unpack_from(janela))
    return _GIRO.pack(*eixos) + janela[_GIRO.size:]


def janela_que_sai(uniq: str | None, janela: bytes) -> bytes:
    """A janela de movimento como sai para a peça ``uniq``: os sensores da peça e o peso da mira."""
    return pesar_a_janela(REGISTRO.filtrar(uniq, janela), PESO_DA_MIRA.ganho(uniq))


def _saturar(valor: int) -> int:
    """O eixo nunca sai de 0..255 — o kernel clampa, mas quem afirma é a casa."""
    return max(EIXO_MIN, min(EIXO_MAX, valor))


def misturar(eixo_h: int, eixo_v: int, dh: int, dv: int) -> tuple[int, int]:
    """Soma o giro ao analógico FÍSICO, com saturação."""
    return _saturar(eixo_h + dh), _saturar(eixo_v + dv)


def pixels(
    angulo: tuple[float, float, float],
    arranjo: ArranjoDeMovimento,
    ganho: float = 1.0,
    gravidade: tuple[float, float, float] | None = None,
) -> tuple[float, float]:
    """Ângulo percorrido (graus) → deslocamento de cursor, em pixels FLOAT."""
    if not arranjo.ligado:
        return 0.0, 0.0
    horizontal, vertical = _componentes(angulo, arranjo, gravidade)
    fator = arranjo.pixels_por_grau * ganho / SENSIBILIDADE_PADRAO
    return horizontal * fator * arranjo.sensibilidade_h, vertical * fator * arranjo.sensibilidade_v


def montar(secao: object) -> ArranjoDeMovimento:
    """A seção do perfil vira arranjo SEMPRE — inclusive com o destino `nenhum`."""
    destino = str(getattr(secao, "destino", DESTINO_NENHUM) or DESTINO_NENHUM)
    if destino not in DESTINOS:
        raise ArranjoRecusadoError(
            f"destino desconhecido: {destino!r} (conhecidos: {', '.join(DESTINOS)})"
        )
    zona = float(getattr(secao, "zona_morta_graus_s", ZONA_MORTA_PADRAO_GRAUS_S))
    velocidade = float(getattr(secao, "velocidade_do_jogo", VELOCIDADE_DO_JOGO_PADRAO_GRAUS_S))
    if velocidade <= 0.0:
        raise ArranjoRecusadoError(
            f"a velocidade do jogo ({velocidade}°/s) tem de ser maior que zero"
        )
    sens_h = int(getattr(secao, "sensibilidade_h", SENSIBILIDADE_PADRAO))
    sens_v = int(getattr(secao, "sensibilidade_v", SENSIBILIDADE_PADRAO))
    toque = str(getattr(secao, "toque", DESTINO_NENHUM) or DESTINO_NENHUM)
    if toque not in TOQUES:
        raise ArranjoRecusadoError(
            f"toque desconhecido: {toque!r} (conhecidos: {', '.join(TOQUES)})"
        )
    lado = str(getattr(secao, "lado", DESTINO_ANALOGICO_DIREITO) or DESTINO_ANALOGICO_DIREITO)
    if lado not in LADOS_DO_VIRTUAL:
        raise ArranjoRecusadoError(
            f"lado do analógico virtual desconhecido: {lado!r} "
            f"(conhecidos: {', '.join(LADOS_DO_VIRTUAL)})"
        )
    return ArranjoDeMovimento(
        destino=destino,
        sensibilidade_h=max(SENSIBILIDADE_MIN, min(SENSIBILIDADE_MAX, sens_h)),
        sensibilidade_v=max(SENSIBILIDADE_MIN, min(SENSIBILIDADE_MAX, sens_v)),
        inverter_horizontal=bool(getattr(secao, "inverter_horizontal", False)),
        inverter_vertical=bool(getattr(secao, "inverter_vertical", False)),
        zona_morta_graus_s=zona,
        velocidade_do_jogo=velocidade,
        piso=max(0.0, min(1.0, float(getattr(secao, "piso", PISO_PADRAO)))),
        pixels_por_grau=float(
            getattr(secao, "pixels_por_grau", PIXELS_POR_GRAU_PADRAO)
        ),
        gatilho=(getattr(secao, "gatilho", None) or None),
        toque=toque,
        mesmo_parado=bool(getattr(secao, "mesmo_parado", False)),
        lado=lado,
    )


def lado_do_virtual(arranjo: ArranjoDeMovimento) -> str:
    """O lado que a tela acende: o do giro; sem giro num analógico, o guardado."""
    return arranjo.destino if arranjo.destino in LADOS_DO_VIRTUAL else arranjo.lado


def virtual_aceso(arranjo: ArranjoDeMovimento) -> bool:
    """O Analógico Virtual está aceso: o giro move um analógico.

    O `mouse` não conta: o giro no cursor não é lado de analógico.
    """
    return arranjo.destino in LADOS_DO_VIRTUAL


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
    """Os campos que a seção DIZ — só os escritos, quando a seção sabe distinguir."""
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
    """O arranjo de UMA peça: a seção da peça campo a campo por cima da do perfil."""
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
    """Troca a opinião de UMA peça, e só dessa peça — o gesto do chip, ao vivo."""
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
    """Diz ao braço do REPORT quais peças estão mirando — o giro nativo sai dessas peças."""
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
    """O ângulo que a peça acabou de drenar, ou `None` se ele é um acumulado.

    O ângulo é a integral do giro CRU: sai daqui sem o viés do zero que o «Começar» da
    Calibrar guardou (`viés x dt`, nos três eixos, com o `dt` da drenagem anterior), a
    mesma conta que `descontar_o_vies` faz na velocidade. Sem zero, o mesmo objeto.
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
    zero = zero_de(dono, uniq)
    if zero is None:
        return angulo
    dt = agora - anterior
    vies = zero.giro
    return (
        float(angulo[0]) - vies[0] * dt,
        float(angulo[1]) - vies[1] * dt,
        float(angulo[2]) - vies[2] * dt,
    )


SILENCIO_DA_AMOSTRA_S: Final = 0.050

_ATRIBUTO_DA_MIRA: Final = "_roteador_de_movimento_mira"

_PARADO: Final[tuple[float, float, float]] = (0.0, 0.0, 0.0)


@dataclass(slots=True)
class _Mira:
    """O que a mira lembra de UMA peça entre dois tiques: nada aqui é da mesa."""

    velocidade: tuple[float, float, float] = _PARADO
    amostra_em: float = -math.inf
    gravidade: tuple[float, float, float] | None = None
    gravidade_em: float = -math.inf
    resto_h: float = 0.0
    resto_v: float = 0.0


def _mira_da_peca(dono: object, uniq: str) -> _Mira:
    if dono is None:
        return _Mira()
    mapa = getattr(dono, _ATRIBUTO_DA_MIRA, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DA_MIRA, mapa)
    chave = chave_de_sensor(uniq)
    estado = mapa.get(chave)
    if not isinstance(estado, _Mira):
        estado = _Mira()
        mapa[chave] = estado
    return estado


def velocidade_do_tique(
    dono: object,
    uniq: str,
    lido: tuple[tuple[float, float, float], float] | None,
    agora: float,
) -> tuple[float, float, float] | None:
    """A média do giro no tique: o ângulo drenado sobre o tempo do kernel, sem o viés do zero.

    `lido` é o `(ângulo, segundos)` do hub. Tique sem amostra repete a última velocidade por até
    `SILENCIO_DA_AMOSTRA_S`, e depois vai a zero, para o analógico nunca ficar preso numa queda.
    Trecho maior que `SILENCIO_DA_DRENAGEM_S` é o que acumulou enquanto ninguém drenava.
    """
    if lido is None:
        return None
    angulo, segundos = lido
    estado = _mira_da_peca(dono, uniq)
    if segundos > SILENCIO_DA_DRENAGEM_S:
        estado.velocidade = _PARADO
        estado.amostra_em = agora
        estado.resto_h = estado.resto_v = 0.0
        return _PARADO
    if segundos <= 0.0:
        if agora - estado.amostra_em <= SILENCIO_DA_AMOSTRA_S:
            return estado.velocidade
        return _PARADO
    velocidade = descontar_o_vies(
        dono, uniq, (angulo[0] / segundos, angulo[1] / segundos, angulo[2] / segundos)
    )
    if velocidade is None:
        return None
    estado.velocidade = velocidade
    estado.amostra_em = agora
    return velocidade


def gravidade_do_tique(
    dono: object, uniq: str, acel: tuple[float, float, float] | None, agora: float
) -> tuple[float, float, float] | None:
    """A gravidade filtrada da peça, unitária; o filtro anda por tempo, nunca por amostra."""
    estado = _mira_da_peca(dono, uniq)
    leitura = _unitario(acel) if acel is not None else None
    if leitura is None:
        return estado.gravidade
    decorrido = agora - estado.gravidade_em
    estado.gravidade_em = agora
    anterior = estado.gravidade
    if anterior is None or decorrido > SILENCIO_DA_DRENAGEM_S:
        estado.gravidade = leitura
        return leitura
    peso = 1.0 - math.exp(-max(0.0, decorrido) / TEMPO_DA_GRAVIDADE_S)
    misturada = (
        anterior[0] + (leitura[0] - anterior[0]) * peso,
        anterior[1] + (leitura[1] - anterior[1]) * peso,
        anterior[2] + (leitura[2] - anterior[2]) * peso,
    )
    estado.gravidade = _unitario(misturada) or leitura
    return estado.gravidade


def deflexao_do_tique(
    dono: object,
    uniq: str,
    velocidade: tuple[float, float, float],
    arranjo: ArranjoDeMovimento,
    ganho: float = 1.0,
    gravidade: tuple[float, float, float] | None = None,
) -> tuple[int, int]:
    """Velocidade angular (graus/s) → deslocamento a SOMAR num analógico, eixo a eixo.

    O que o arredondamento perde vai ao tique seguinte, por eixo.
    """
    horizontal, vertical = _deflexao_exata(velocidade, arranjo, ganho, gravidade)
    estado = _mira_da_peca(dono, uniq)
    dh, estado.resto_h = _com_o_resto(horizontal, estado.resto_h)
    dv, estado.resto_v = _com_o_resto(vertical, estado.resto_v)
    return dh, dv


def _com_o_resto(valor: float, resto: float) -> tuple[int, float]:
    if valor == 0.0:
        return 0, 0.0
    total = valor + resto
    inteiro = round(total)
    return inteiro, total - inteiro


def zerar_o_resto(dono: object, uniq: str) -> None:
    """A mira da peça fechou: a próxima ativação nasce sem o resto da anterior."""
    estado = _mira_da_peca(dono, uniq)
    estado.resto_h = estado.resto_v = 0.0


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

_ATRIBUTO_DO_REPOUSO: Final = "_roteador_de_movimento_repouso"
_ATRIBUTO_DO_DEDO: Final = "_roteador_de_movimento_ultimo_dedo"


def _unitario(vetor: tuple[float, float, float]) -> tuple[float, float, float] | None:
    x, y, z = (float(v) for v in vetor)
    modulo = math.sqrt(x * x + y * y + z * z)
    if modulo < GRAVIDADE_MINIMA_G:
        return None
    return x / modulo, y / modulo, z / modulo


VARIACAO_DO_PARADO_GRAUS_S: Final = 1.5
GRAVIDADE_DO_PARADO_GRAUS: Final = 2.0
TEMPO_DO_PARADO_S: Final = 3.0
SAIDA_DO_PARADO_GRAUS: Final = 3.0
GIRO_DA_PEGADA_GRAUS_S: Final = 20.0
TEMPO_DA_PEGADA_S: Final = 0.25


@dataclass(slots=True)
class _Repouso:
    """O que a regra lembra de UMA peça entre dois tiques."""

    carimbo: float
    inicio: float
    menor: list[float]
    maior: list[float]
    gravidade_do_inicio: tuple[float, float, float]
    virgem: bool = True
    parado: bool = False
    gravidade_do_parado: tuple[float, float, float] | None = None
    pegando_desde: float | None = None


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


def _a_mao_pegou(
    estado: _Repouso, giro: tuple[float, float, float], acel: tuple[float, float, float],
    agora: float,
) -> bool:
    """A peça parada só sai do parado com movimento que dura: o esbarrão passa e não conta.

    Mexer é a gravidade longe da que parou ou o giro acima de `GIRO_DA_PEGADA_GRAUS_S`, e a
    saída pede `TEMPO_DA_PEGADA_S` de mexer sem pausa.
    """
    base = estado.gravidade_do_parado
    mexe = (
        base is None
        or _graus_entre(acel, base) >= SAIDA_DO_PARADO_GRAUS
        or math.sqrt(sum(float(v) * float(v) for v in giro)) >= GIRO_DA_PEGADA_GRAUS_S
    )
    if not mexe:
        estado.pegando_desde = None
        return False
    if estado.pegando_desde is None:
        estado.pegando_desde = agora
    if agora - estado.pegando_desde < TEMPO_DA_PEGADA_S:
        return False
    estado.pegando_desde = None
    return True


def parada_agora(
    dono: object,
    uniq: str,
    giro: tuple[float, float, float],
    acel: tuple[float, float, float] | None,
    agora: float,
    *,
    mesmo_parado: bool = False,
) -> bool:
    """A peça está largada: a mira fica calada, e um esbarrão não rouba a vez no jogo.

    Parada é o giro variando menos de `VARIACAO_DO_PARADO_GRAUS_S` de pico a pico em cada eixo e
    a gravidade andando menos de `GRAVIDADE_DO_PARADO_GRAUS`, por `TEMPO_DO_PARADO_S`. A saída é
    a de `_a_mao_pegou`. `mesmo_parado` (o «Mesmo parado» da Calibrar) nunca para.
    """
    if dono is None:
        return False
    mapa = getattr(dono, _ATRIBUTO_DO_REPOUSO, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DO_REPOUSO, mapa)
    chave = chave_de_sensor(uniq)
    leitura = _PARADO if acel is None else acel
    estado = mapa.get(chave)
    if not isinstance(estado, _Repouso) or agora - estado.carimbo > SILENCIO_DA_DRENAGEM_S:
        estado = _Repouso(
            carimbo=agora, inicio=agora, menor=[float(v) for v in giro],
            maior=[float(v) for v in giro], gravidade_do_inicio=leitura,
        )
        mapa[chave] = estado
    else:
        estado.carimbo = agora
    if mesmo_parado:
        estado.parado = False
        _recomecar_a_janela(estado, giro, leitura, agora)
        return False
    if estado.parado:
        if _a_mao_pegou(estado, giro, leitura, agora):
            estado.parado = False
            _recomecar_a_janela(estado, giro, leitura, agora)
        return estado.parado
    _o_tique_da_janela(estado, giro, leitura, agora)
    return estado.parado


def mira_parada(dono: object, uniq: str, agora: float) -> bool:
    """A última resposta da regra para esta peça: parada agora (o chip meio apagado).

    Sem tique há mais de `SILENCIO_DA_DRENAGEM_S` (a rota apagou, o controle saiu),
    a resposta é falsa: a regra não mede o que não lê.
    """
    mapa = getattr(dono, _ATRIBUTO_DO_REPOUSO, None)
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
    """O dedo que andou vira pixels de cursor; o 0 da mira não desliga o dedo."""
    fator = PIXELS_POR_UNIDADE_DO_TOQUE / SENSIBILIDADE_PADRAO
    return (
        dx * fator * max(1, arranjo.sensibilidade_h),
        dy * fator * max(1, arranjo.sensibilidade_v),
    )


def quer_cursor(dono: object) -> bool:
    """Alguma peça leva o touchpad ao cursor agora? É a pergunta do dono do nó."""
    mesa = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if type(mesa) is ArranjoDeMovimento and mesa.toque == TOQUE_CURSOR:
        return True
    return any(
        type(v) is ArranjoDeMovimento and v.toque == TOQUE_CURSOR
        for v in por_peca(dono).values()
    )


SEGUNDOS_DO_ZERO: Final = 5.0
MINIMO_DE_AMOSTRAS_DO_ZERO: Final = 20
FRACAO_QUIETA_DO_ZERO: Final = TEMPO_DO_PARADO_S / SEGUNDOS_DO_ZERO

_ATRIBUTO_DO_ZERO: Final = "_roteador_de_movimento_zero"

Vetor = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ZeroDoControle:
    """O repouso medido de UM controle: o viés do giro (°/s)."""

    giro: Vetor


def _media(vetores: Sequence[Vetor]) -> Vetor:
    n = float(len(vetores))
    return (
        sum(float(v[0]) for v in vetores) / n,
        sum(float(v[1]) for v in vetores) / n,
        sum(float(v[2]) for v in vetores) / n,
    )


def _trecho_quieto(lista: Sequence[tuple[Vetor, Vetor]]) -> Sequence[tuple[Vetor, Vetor]]:
    """O trecho contínuo mais longo em que a peça ficou parada, pela régua do parado."""
    giro0, acel0 = lista[0]
    estado = _Repouso(
        carimbo=0.0, inicio=0.0,
        menor=[float(v) for v in giro0], maior=[float(v) for v in giro0],
        gravidade_do_inicio=acel0,
    )
    inicio, melhor = 0, (0, 1)
    for i, (giro, acel) in enumerate(lista[1:], 1):
        estado.virgem = True
        _o_tique_da_janela(estado, giro, acel, 0.0)
        if not estado.virgem:
            inicio = i
        if i + 1 - inicio > melhor[1] - melhor[0]:
            melhor = (inicio, i + 1)
    return lista[melhor[0]:melhor[1]]


def fracao_quieta(amostras: Sequence[tuple[Vetor, Vetor]]) -> float:
    """Quanto da medida a peça passou parada, de 0 a 1, para o diário."""
    lista = list(amostras)
    return len(_trecho_quieto(lista)) / len(lista) if lista else 0.0


def medir_o_zero(amostras: Sequence[tuple[Vetor, Vetor]]) -> ZeroDoControle | None:
    """O zero de uma peça a partir das amostras `(giro, acel)` da medida; `None` se mexeu.

    A régua é a do parado: a janela quieta que recomeça quando o giro varia mais de
    `VARIACAO_DO_PARADO_GRAUS_S` de pico a pico ou a gravidade anda mais de
    `GRAVIDADE_DO_PARADO_GRAUS`. Vale o trecho quieto mais longo, se durou ao menos os
    `TEMPO_DO_PARADO_S` que a mesma régua exige: quem clica em Começar e solta o controle na mesa
    mexe nele no começo da medida, e o repouso que vem depois é um repouso de verdade.
    """
    lista = list(amostras)
    if len(lista) < MINIMO_DE_AMOSTRAS_DO_ZERO:
        return None
    quieto = _trecho_quieto(lista)
    minimo = len(lista) * FRACAO_QUIETA_DO_ZERO
    if len(quieto) < max(MINIMO_DE_AMOSTRAS_DO_ZERO, minimo):
        return None
    return ZeroDoControle(giro=_media([g for g, _ in quieto]))


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
    """Os zeros guardados, na forma do arquivo: chave de sensor → giro."""
    mapa = getattr(dono, _ATRIBUTO_DO_ZERO, None)
    if not isinstance(mapa, dict):
        return {}
    return {
        chave: {"giro": list(zero.giro)}
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
    """Devolve ao `dono` os zeros lidos do arquivo; a entrada torta fica de fora.

    A gravidade que o arquivo antigo traz não se lê e não volta ao disco.
    """
    if dono is None or not isinstance(dados, Mapping):
        return 0
    contados = 0
    for chave, valor in dados.items():
        if not isinstance(valor, Mapping):
            continue
        giro = _vetor(valor.get("giro"))
        if giro is None or not chave_de_sensor(str(chave)):
            continue
        definir_o_zero(dono, str(chave), ZeroDoControle(giro=giro))
        contados += 1
    return contados


SEGUNDOS_DO_SINAL: Final = 3.0
GIRO_DO_SINAL_GRAUS: Final = 15.0
SINAL_BATEU: Final = "bateu"
SINAL_CONTRARIO: Final = "contrario"
SINAL_PARADO: Final = "parado"
TEMPO_DA_RAMPA_S: Final = 12.0
TETO_DA_RAMPA: Final = 0.6
_ATRIBUTO_DA_RAMPA: Final = "_roteador_de_movimento_rampa"


def _primeiro_sentido(valores: Sequence[float], passo: float) -> int:
    """O sinal do ângulo somado ao cruzar `GIRO_DO_SINAL_GRAUS`; 0 se nunca cruzou."""
    soma = 0.0
    for valor in valores:
        soma += valor * passo
        if abs(soma) >= GIRO_DO_SINAL_GRAUS:
            return -1 if soma < 0.0 else 1
    return 0


def _veredito_do_eixo(sentido: int) -> str:
    if sentido == 0:
        return SINAL_PARADO
    return SINAL_BATEU if sentido < 0 else SINAL_CONTRARIO


def conferir_o_sinal(
    amostras: Sequence[tuple[Vetor, Vetor | None]], arranjo: ArranjoDeMovimento, passo: float
) -> dict[str, str]:
    """O gesto guiado contra o arranjo: virar à esquerda e levantar o nariz.

    Os dois gestos têm de levar o analógico à esquerda e para cima, com o `inverter` da peça
    já aplicado. Nada se grava aqui: o que fica é o veredito, e quem quer o contrário usa o
    `inverter`.
    """
    memoria = SimpleNamespace()
    horizontais: list[float] = []
    verticais: list[float] = []
    agora = 0.0
    for giro, acel in amostras:
        agora += passo
        gravidade = gravidade_do_tique(memoria, "sinal", acel, agora)
        horizontal, vertical = _componentes(giro, arranjo, gravidade)
        horizontais.append(horizontal)
        verticais.append(vertical)
    do_lado = _veredito_do_eixo(_primeiro_sentido(horizontais, passo))
    do_nariz = _veredito_do_eixo(_primeiro_sentido(verticais, passo))
    vereditos = {do_lado, do_nariz}
    if SINAL_PARADO in vereditos:
        estado = SINAL_PARADO
    elif SINAL_CONTRARIO in vereditos:
        estado = SINAL_CONTRARIO
    else:
        estado = SINAL_BATEU
    return {"estado": estado, "horizontal": do_lado, "vertical": do_nariz}


def _rampas(dono: object) -> dict[str, float]:
    mapa = getattr(dono, _ATRIBUTO_DA_RAMPA, None)
    if not isinstance(mapa, dict):
        mapa = {}
        setattr(dono, _ATRIBUTO_DA_RAMPA, mapa)
    return mapa


def comecar_a_rampa(dono: object, uniq: str, agora: float) -> None:
    """Começa a rampa no analógico desta peça."""
    _rampas(dono)[chave_de_sensor(uniq)] = agora


def rampa_agora(dono: object, uniq: str | None, agora: float) -> float | None:
    """A fração do analógico que a rampa desta peça pede agora; `None` sem rampa viva.

    Passado `TEMPO_DA_RAMPA_S` a rampa some sozinha: ninguém disse que andou, e o analógico volta.
    """
    mapa = getattr(dono, _ATRIBUTO_DA_RAMPA, None)
    if not isinstance(mapa, dict) or not uniq:
        return None
    chave = chave_de_sensor(uniq)
    inicio = mapa.get(chave)
    if inicio is None:
        return None
    passou = agora - inicio
    if passou >= TEMPO_DA_RAMPA_S:
        del mapa[chave]
        return None
    return float(TETO_DA_RAMPA * max(0.0, passou) / TEMPO_DA_RAMPA_S)


def parar_a_rampa(dono: object, uniq: str, agora: float) -> float | None:
    """Encerra a rampa desta peça e devolve o ponto em que estava; `None` se não havia."""
    valor = rampa_agora(dono, uniq, agora)
    mapa = getattr(dono, _ATRIBUTO_DA_RAMPA, None)
    if isinstance(mapa, dict):
        mapa.pop(chave_de_sensor(uniq), None)
    return valor


def deflexao_da_rampa(valor: float) -> tuple[int, int]:
    """A fração da rampa em `(dh, dv)`: o analógico anda só para a direita."""
    return round(valor * 127), 0


EIXOS_DA_SONY: Final[tuple[tuple[int, float], ...]] = ((0, 1.0), (1, 1.0), (2, 1.0))
ORIENTACAO_MEDIDA: Final[dict[str, tuple[tuple[int, float], ...]]] = {"sony": EIXOS_DA_SONY}


def orientar(familia: str | None, vetor: Vetor) -> Vetor | None:
    """O vetor do sensor no referencial da Sony; `None` na família sem gesto medido.

    Cada linha da `ORIENTACAO_MEDIDA` diz, para x, y e z da Sony, o eixo da família e o sinal.
    Só entra família medida no aparelho. Sem família (o dublê, o nó ainda fechado) vale a Sony.
    """
    eixos = EIXOS_DA_SONY if familia is None else ORIENTACAO_MEDIDA.get(familia)
    if eixos is None:
        return None
    if eixos is EIXOS_DA_SONY:
        return vetor
    x, y, z = (vetor[eixo] * sinal for eixo, sinal in eixos)
    return (x, y, z)


__all__ = [
    "BOTAO_DA_ZONA_DE_BAIXO",
    "BOTAO_DA_ZONA_DE_CIMA",
    "CAMPOS",
    "CENTRO_DO_EIXO",
    "DEFLEXAO_MAXIMA",
    "DESTINOS",
    "DESTINO_ANALOGICO_DIREITO",
    "DESTINO_ANALOGICO_ESQUERDO",
    "DESTINO_MOUSE",
    "DESTINO_NENHUM",
    "FRACAO_DO_DIRECIONAL",
    "GANHO_MINIMO_DA_MIRA",
    "GANHO_NA_SENSIBILIDADE_PADRAO",
    "GIRO_DA_PEGADA_GRAUS_S",
    "GRAVIDADE_DE_BASE",
    "GRAVIDADE_DO_PARADO_GRAUS",
    "GRAVIDADE_MINIMA_G",
    "MENOR_PLANO_DA_GRAVIDADE",
    "MINIMO_DE_AMOSTRAS_DO_ZERO",
    "MIOLO_DO_DIRECIONAL",
    "ORIENTACAO_MEDIDA",
    "PESO_DA_MIRA",
    "PISO_PADRAO",
    "PIXELS_POR_GRAU_PADRAO",
    "PIXELS_POR_UNIDADE_DO_TOQUE",
    "PRAZO_MAXIMO_DO_PESO_MS",
    "RUIDO_DO_GIRO_GRAUS_S",
    "SAIDA_DO_PARADO_GRAUS",
    "SEGUNDOS_DO_SINAL",
    "SEGUNDOS_DO_ZERO",
    "SENSIBILIDADE_MAX",
    "SENSIBILIDADE_MIN",
    "SENSIBILIDADE_PADRAO",
    "SILENCIO_DA_AMOSTRA_S",
    "SILENCIO_DA_DRENAGEM_S",
    "SINAL_BATEU",
    "SINAL_CONTRARIO",
    "SINAL_PARADO",
    "SO_NAS_PECAS",
    "TEMPO_DA_GRAVIDADE_S",
    "TEMPO_DA_PEGADA_S",
    "TEMPO_DA_RAMPA_S",
    "TEMPO_DO_PARADO_S",
    "TETO_DA_RAMPA",
    "TODOS_OS_CONTROLES",
    "TOQUES",
    "TOQUE_CURSOR",
    "TOQUE_ZONAS",
    "VARIACAO_DO_PARADO_GRAUS_S",
    "VELOCIDADE_DO_JOGO_PADRAO_GRAUS_S",
    "ZONA_MORTA_PADRAO_GRAUS_S",
    "ArranjoDeMovimento",
    "ArranjoRecusadoError",
    "PesoDaMira",
    "ZeroDoControle",
    "angulo_do_tique",
    "arranjo_da_peca",
    "ativo",
    "botoes_das_zonas",
    "carregar_os_zeros",
    "comecar_a_rampa",
    "conferir_o_sinal",
    "da_peca",
    "definir_ativo",
    "definir_da_peca",
    "definir_o_zero",
    "definir_por_peca",
    "deflexao_da_rampa",
    "deflexao_do_tique",
    "delta_do_toque",
    "descontar_o_vies",
    "fracao_quieta",
    "gravidade_do_tique",
    "janela_que_sai",
    "medir_o_zero",
    "mira_parada",
    "misturar",
    "montar",
    "orientar",
    "para_o_cursor",
    "parada_agora",
    "parametros_da_peca",
    "parar_a_rampa",
    "passa_da_zona_morta",
    "pecas_que_miram",
    "pesar_a_janela",
    "pixels",
    "pixels_do_toque",
    "por_peca",
    "quer_cursor",
    "rampa_agora",
    "sincronizar_o_filtro",
    "velocidade_do_tique",
    "zerar_o_resto",
    "zero_de",
    "zeros_para_gravar",
]
