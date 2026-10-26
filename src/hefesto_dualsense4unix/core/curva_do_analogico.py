"""Os analógicos do jogo: zona morta, curva, sensibilidade, inversão, troca e uma mão só.

Dono único e puro. O mesmo módulo serve o pad virtual do primeiro controle e o dos outros
jogadores, e entra DEPOIS do giro feito analógico (a mesma curva vale para os dois). O padrão
é a identidade, byte a byte, de 0 a 255. Cada analógico é moldado como o aparelho o entrega
(zona morta radial, curva, sensibilidade), depois invertido, e só então os dois lados trocam.
A mão esquerda e a direita são predefinições: dizem quem troca e para que lado o giro olha.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

CENTRO: Final = 128
CURVAS: Final[tuple[str, ...]] = ("linear", "precisa", "estavel", "digital")
EIXOS: Final[tuple[str, ...]] = ("lx", "ly", "rx", "ry")
MAOS: Final[tuple[str, ...]] = ("esquerda", "direita")

FAIXA_DA_ZONA_MORTA: Final = (0, 50)
FAIXA_DA_ZONA_EXTERNA: Final = (0, 30)
FAIXA_DA_SENSIBILIDADE: Final = (50, 150)
FAIXA_DO_GATILHO: Final = (0, 40)

CAMPOS: Final[tuple[str, ...]] = (
    "zona_morta", "zona_externa", "curva", "sensibilidade", "inverter", "trocar",
    "mao",  # (noqa-acento)
    "gatilho_inicio", "gatilho_fim",
)

_ATRIBUTO_DA_MESA: Final = "_curva_do_analogico_da_mesa"
_ATRIBUTO_POR_PECA: Final = "_curva_do_analogico_por_peca"


@dataclass(frozen=True, slots=True)
class Curva:
    """O que vale para UM controle. Tudo em fração (0 a 1), a sensibilidade em torno de 1."""

    zona_interna: float = 0.0
    zona_externa: float = 0.0
    forma: str = "linear"
    sensibilidade: float = 1.0
    inverter: frozenset[str] = frozenset()
    trocar: bool = False
    mao: str | None = None
    gatilho_inicio: float = 0.0
    gatilho_fim: float = 0.0

    @property
    def troca(self) -> bool:
        """Os dois lados trocam de lugar: pedido ou pela mão direita."""
        return self.trocar or self.mao == "direita"

    @property
    def molda(self) -> bool:
        """Algo a fazer na forma do analógico (zona morta, curva ou sensibilidade)."""
        return (
            self.zona_interna > 0 or self.zona_externa > 0
            or self.forma != "linear" or self.sensibilidade != 1.0
        )

    @property
    def algum(self) -> bool:
        return (
            self.molda or bool(self.inverter) or self.troca
            or self.gatilho_inicio > 0 or self.gatilho_fim > 0 or self.mao is not None
        )


def recusar(trocar: object, mao: object) -> str:
    """A mão já decide a troca; pedir a troca por cima da mão é pedir duas coisas."""
    if mao and trocar:
        return f"a mão {mao} é uma predefinição que já decide a troca dos analógicos"
    return ""


def escritos(secao: object) -> dict[str, Any]:
    """Só o que a seção DIZ (quando ela sabe distinguir o escrito do default)."""
    if secao is None:
        return {}
    dito = getattr(secao, "model_fields_set", None)
    nomes = CAMPOS if dito is None else tuple(n for n in CAMPOS if n in dito)
    return {n: getattr(secao, n) for n in nomes if hasattr(secao, n)}


def campos_juntos(secao: object, secao_da_peca: object = None) -> dict[str, Any]:
    """A seção do perfil com a da peça por cima campo a campo; se a soma recusa, só a da peça."""
    da_peca_ = escritos(secao_da_peca)
    campos = {**escritos(secao), **da_peca_}
    if recusar(campos.get("trocar"), campos.get("mao")):  # (noqa-acento)
        return da_peca_
    return campos


def _pct(valor: object, faixa: tuple[int, int], padrao: int = 0) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        valor = padrao
    return min(max(int(valor), faixa[0]), faixa[1]) / 100.0


def montar(secao: object, secao_da_peca: object = None) -> Curva | None:
    """A curva do perfil, com a da peça por cima campo a campo. ``None`` = identidade."""
    campos = campos_juntos(secao, secao_da_peca)
    if not campos:
        return None
    forma = str(campos.get("curva") or "linear")
    mao = campos.get("mao")  # (noqa-acento)
    curva = Curva(
        zona_interna=_pct(campos.get("zona_morta"), FAIXA_DA_ZONA_MORTA),
        zona_externa=_pct(campos.get("zona_externa"), FAIXA_DA_ZONA_EXTERNA),
        forma=forma if forma in CURVAS else "linear",
        sensibilidade=_pct(campos.get("sensibilidade"), FAIXA_DA_SENSIBILIDADE, 100),
        inverter=frozenset(n for n in (campos.get("inverter") or ()) if n in EIXOS),
        trocar=campos.get("trocar") is True,
        mao=str(mao) if mao in MAOS else None,
        gatilho_inicio=_pct(campos.get("gatilho_inicio"), FAIXA_DO_GATILHO),
        gatilho_fim=_pct(campos.get("gatilho_fim"), FAIXA_DO_GATILHO),
    )
    return curva if curva.algum else None


def _forma(forma: str, t: float) -> float:
    """A curva de 0 a 1 em 0 a 1. A precisa afina o começo, a estável o suaviza, a digital corta."""
    if forma == "precisa":
        return t * t
    if forma == "estavel":
        return t * t * (3.0 - 2.0 * t)
    if forma == "digital":
        return 1.0 if t >= 0.5 else 0.0
    return t


def _para_fracao(valor: int) -> float:
    return (valor - CENTRO) / (127.0 if valor >= CENTRO else 128.0)


def _para_byte(fracao: float) -> int:
    byte = CENTRO + round(fracao * (127.0 if fracao >= 0 else 128.0))
    return min(max(byte, 0), 255)


def moldar(curva: Curva, x: int, y: int) -> tuple[int, int]:
    """Zona morta radial, curva e sensibilidade de UM analógico. Sem nada disso, a identidade."""
    if not curva.molda:
        return x, y
    fx, fy = _para_fracao(x), _para_fracao(y)
    modulo = math.hypot(fx, fy)
    if modulo <= curva.zona_interna or modulo == 0.0:
        return CENTRO, CENTRO
    util = 1.0 - curva.zona_interna - curva.zona_externa
    t = min(max((modulo - curva.zona_interna) / util, 0.0), 1.0) if util > 0 else 1.0
    saida = min(_forma(curva.forma, t) * curva.sensibilidade, 1.0)
    return _para_byte(fx / modulo * saida), _para_byte(fy / modulo * saida)


def _invertido(valor: int) -> int:
    """Espelha em torno do centro: o 0 vira 255 (o 256 não cabe) e o 128 fica onde está."""
    return min(2 * CENTRO - valor, 255)


def gatilho(curva: Curva, valor: int) -> int:
    """Zona morta de início e de fim do gatilho (0 a 255)."""
    if curva.gatilho_inicio <= 0 and curva.gatilho_fim <= 0:
        return valor
    inicio = curva.gatilho_inicio * 255.0
    fim = 255.0 - curva.gatilho_fim * 255.0
    if valor <= inicio:
        return 0
    if valor >= fim:
        return 255
    return min(max(round((valor - inicio) * 255.0 / (fim - inicio)), 0), 255)


def analogicos(
    curva: Curva, lx: int, ly: int, rx: int, ry: int
) -> tuple[int, int, int, int]:
    """Molda cada lado, inverte o que foi pedido e, por último, troca os lados."""
    lx, ly = moldar(curva, lx, ly)
    rx, ry = moldar(curva, rx, ry)
    if curva.inverter:
        lx = _invertido(lx) if "lx" in curva.inverter else lx
        ly = _invertido(ly) if "ly" in curva.inverter else ly
        rx = _invertido(rx) if "rx" in curva.inverter else rx
        ry = _invertido(ry) if "ry" in curva.inverter else ry
    if curva.troca:
        return rx, ry, lx, ly
    return lx, ly, rx, ry


def chave(uniq: object) -> str:
    """A identidade do controle: só os hex, em minúsculas (a mesma do modo do botão).

    O perfil guarda a peça pelos 12 hex e o laço pergunta pelo endereço com dois-pontos: sem
    esta normalização a curva POR PEÇA nunca era achada e só valia a do perfil inteiro.
    """
    return "".join(c for c in str(uniq or "").lower() if c in "0123456789abcdef")


def definir_ativo(
    dono: object,
    mesa: Curva | None,
    por_peca: Mapping[str, Curva | None] | None = None,
) -> None:
    """Guarda a curva ATIVA no dono (o ``StateStore``): a do perfil e a de cada controle."""
    if dono is None:
        return
    setattr(dono, _ATRIBUTO_DA_MESA, mesa)
    limpo = {chave(k): v for k, v in (por_peca or {}).items() if chave(k)}
    setattr(dono, _ATRIBUTO_POR_PECA, MappingProxyType(limpo))


def da_peca(dono: object, uniq: object) -> Curva | None:
    """A curva que vale para o controle ``uniq`` AGORA, ou ``None`` (a identidade)."""
    mapa = getattr(dono, _ATRIBUTO_POR_PECA, None)
    if isinstance(mapa, Mapping) and uniq:
        k = chave(uniq)
        if k in mapa:
            valor = mapa[k]
            return valor if isinstance(valor, Curva) and valor.algum else None
    mesa = getattr(dono, _ATRIBUTO_DA_MESA, None)
    return mesa if isinstance(mesa, Curva) and mesa.algum else None


def alguma(dono: object) -> bool:
    """Algum controle tem curva neste perfil? Custo de dois ``getattr`` no tique."""
    mesa = getattr(dono, _ATRIBUTO_DA_MESA, None)
    if isinstance(mesa, Curva) and mesa.algum:
        return True
    mapa = getattr(dono, _ATRIBUTO_POR_PECA, None)
    return isinstance(mapa, Mapping) and any(
        isinstance(v, Curva) and v.algum for v in mapa.values())


def aplicar(
    dono: object, uniq: object, lx: int, ly: int, rx: int, ry: int, l2: int, r2: int
) -> tuple[int, int, int, int, int, int]:
    """Os analógicos e os gatilhos do controle ``uniq`` pela curva dele. Sem curva, intactos."""
    curva = da_peca(dono, uniq)
    if curva is None:
        return lx, ly, rx, ry, l2, r2
    lx, ly, rx, ry = analogicos(curva, lx, ly, rx, ry)
    return lx, ly, rx, ry, gatilho(curva, l2), gatilho(curva, r2)


def lado_do_giro(dono: object, uniq: object, destino: str) -> str:
    """Para que analógico o giro vai: a mão escolhida manda o olhar para o lado que sobra.

    A mão esquerda anda no analógico esquerdo e o giro olha pelo direito. A mão direita troca
    os lados DEPOIS do giro, então o giro entra no esquerdo e sai no direito, e o analógico
    que a mão toca sai no esquerdo. Fora de analógico (mouse, nenhum), o destino não muda.
    """
    from hefesto_dualsense4unix.core.roteador_de_movimento import (
        DESTINO_ANALOGICO_DIREITO,
        DESTINO_ANALOGICO_ESQUERDO,
    )

    if destino not in (DESTINO_ANALOGICO_DIREITO, DESTINO_ANALOGICO_ESQUERDO):
        return destino
    curva = da_peca(dono, uniq)
    if curva is None or curva.mao is None:
        return destino
    return DESTINO_ANALOGICO_DIREITO if curva.mao == "esquerda" else DESTINO_ANALOGICO_ESQUERDO


__all__ = [
    "CAMPOS",
    "CURVAS",
    "EIXOS",
    "MAOS",
    "Curva",
    "alguma",
    "analogicos",
    "aplicar",
    "campos_juntos",
    "da_peca",
    "definir_ativo",
    "gatilho",
    "lado_do_giro",
    "moldar",
    "montar",
    "recusar",
]
