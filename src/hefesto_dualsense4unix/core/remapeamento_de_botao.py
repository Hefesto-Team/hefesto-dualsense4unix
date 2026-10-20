"""O remapeamento botão a botão — o motor puro. F1-REMAPEAR, 13/09/2026."""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, cast

#: `core/acoes_de_botao.BOTAO_PS` — a régua confere.
BOTAO_PS: Final = "ps"

GATILHOS: Final[Mapping[str, str]] = MappingProxyType({"l2": "l2_btn", "r2": "r2_btn"})

_ID_DO_NOME: Final[Mapping[str, str]] = MappingProxyType(
    {nome: botao for botao, nome in GATILHOS.items()})

#: O QUE A TROCA ALCANÇA, na ordem de `core/acoes_de_botao.BOTOES`: os botões
#: não é importada daqui porque `acoes_de_botao` arrasta
REMAPEAVEIS: Final[tuple[str, ...]] = (
    "cross", "circle", "square", "triangle",
    "l1", "r1", "l2", "r2",
    "l3", "r3",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "options", "create",
)

#: regiões são invenção do modo mouse, e o DualSense só reporta um clique.
DESTINO_TOUCHPAD: Final = "touchpad"

FORA_DO_ALCANCE: Final[Mapping[str, str]] = MappingProxyType({
    "l3_direcao": "a direção do analógico é eixo, não botão",
    "r3_direcao": "a direção do analógico é eixo, não botão",
    "touchpad_left_press": "o clique do touchpad chega ao jogo por outro caminho",
    "touchpad_middle_press": "o clique do touchpad chega ao jogo por outro caminho",
    "touchpad_right_press": "o clique do touchpad chega ao jogo por outro caminho",
    DESTINO_TOUCHPAD: "o clique do touchpad chega ao jogo por outro caminho",
})

MOTIVO_DESCONHECIDO: Final = "desconhecido"
MOTIVO_PS: Final = "ps"
MOTIVO_FORA: Final = "fora"
MOTIVO_COLISAO: Final = "colisao"  # (noqa-acento) código de motivo, não é prosa

FORCA_CHEIA: Final = 255

_ATRIBUTO_DO_ATIVO: Final = "_remapeamento_de_botao_ativo"
_ATRIBUTO_POR_PECA: Final = "_remapeamento_de_botao_por_peca"


class RemapeamentoRecusadoError(ValueError):
    """A recusa, com o motivo e os botões que ela nomeia."""

    def __init__(self, motivo: str, botoes: tuple[str, ...]) -> None:
        self.motivo = motivo
        self.botoes = botoes
        super().__init__(f"remapeamento recusado ({motivo}): {', '.join(botoes)}")


def _ordem(botao: str) -> int:
    """A posição da linha na tela, para a recusa nomear na ordem que ela lê."""
    try:
        return REMAPEAVEIS.index(botao)
    except ValueError:
        return len(REMAPEAVEIS)


def resolver(declarado: Mapping[str, str] | None) -> dict[str, str]:
    """O mapa declarado, limpo — ou `RemapeamentoRecusadoError` com o motivo."""
    if not declarado:
        return {}
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES

    conhecidos = set(BOTOES) | {DESTINO_TOUCHPAD}
    limpo = {str(o): str(d) for o, d in declarado.items() if o != d}
    desconhecidos = sorted({x for par in limpo.items() for x in par
                            if x not in conhecidos})
    if desconhecidos or any(o == DESTINO_TOUCHPAD for o in limpo):
        raise RemapeamentoRecusadoError(
            MOTIVO_DESCONHECIDO,
            tuple(desconhecidos) or (DESTINO_TOUCHPAD,))
    com_ps = sorted({o for o, d in limpo.items() if BOTAO_PS in (o, d)}, key=_ordem)
    if com_ps:
        raise RemapeamentoRecusadoError(MOTIVO_PS, tuple(com_ps))
    fora = [o for o, d in limpo.items() if o in FORA_DO_ALCANCE or d in FORA_DO_ALCANCE]
    if fora:
        raise RemapeamentoRecusadoError(MOTIVO_FORA, tuple(sorted(fora, key=_ordem)))
    por_destino: dict[str, list[str]] = {}
    for origem, destino in limpo.items():
        por_destino.setdefault(destino, []).append(origem)
    for destino in sorted(por_destino, key=_ordem):
        origens = por_destino[destino]
        if len(origens) > 1:
            raise RemapeamentoRecusadoError(
                MOTIVO_COLISAO, (*sorted(origens, key=_ordem), destino))
    return limpo


def resolver_da_peca(declarado: Mapping[str, str] | None) -> dict[str, str]:
    """A troca de UM controle, limpa. ``botão: botão`` não troca nada: cancela, só nesta peça,
    a troca que o perfil faz naquele botão (``juntar`` lê isso).
    """
    if not declarado:
        return {}
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES

    conhecidos = set(BOTOES)
    cancela = {str(o): str(d) for o, d in declarado.items() if o == d}
    desconhecidos = sorted(o for o in cancela if o not in conhecidos)
    if desconhecidos:
        raise RemapeamentoRecusadoError(MOTIVO_DESCONHECIDO, tuple(desconhecidos))
    if BOTAO_PS in cancela:
        raise RemapeamentoRecusadoError(MOTIVO_PS, (BOTAO_PS,))
    troca = resolver({o: d for o, d in declarado.items() if o != d})
    return {**troca, **cancela}


def juntar(
    do_perfil: Mapping[str, str] | None, da_peca: Mapping[str, str] | None
) -> dict[str, str]:
    """A troca que vale para o controle: a do perfil, com a da peça por cima, botão a botão.

    O botão que a peça troca vale o que ela diz; o que a peça deixa igual (``botão: botão``)
    volta a passar intacto. Se a soma recusa (dois botões no mesmo destino, por exemplo), vale só
    a da peça: o que o usuário escolheu nunca depende do que o perfil já tinha.
    """
    peca = dict(da_peca or {})
    if not peca:
        return dict(do_perfil or {})
    so_a_dela = {o: d for o, d in peca.items() if o != d}
    soma = {**(do_perfil or {}), **peca}
    soma = {o: d for o, d in soma.items() if o != d}
    try:
        return resolver(soma)
    except RemapeamentoRecusadoError:
        return so_a_dela


def traduzir(
    apertados: frozenset[str], l2: int, r2: int, mapa: Mapping[str, str]
) -> tuple[frozenset[str], int, int]:
    """Um tique: o que o controle apertou → o que o jogo vai ver."""
    saida = {n for n in apertados if _ID_DO_NOME.get(n, n) not in mapa}
    forca = {"l2": 0 if "l2" in mapa else l2, "r2": 0 if "r2" in mapa else r2}
    lida = {"l2": l2, "r2": r2}
    for origem, destino in mapa.items():
        apertado = GATILHOS.get(origem, origem) in apertados
        if destino in GATILHOS:
            valor = lida[origem] if origem in GATILHOS else (
                FORCA_CHEIA if apertado else 0)
            if valor > forca[destino]:
                forca[destino] = valor
            if apertado:
                saida.add(GATILHOS[destino])
        elif apertado:
            saida.add(destino)
    return frozenset(saida), forca["l2"], forca["r2"]


def chave(uniq: object) -> str:
    """A identidade do controle: só os hex, em minúsculas (a mesma da ativação do botão)."""
    return "".join(c for c in str(uniq or "").lower() if c in "0123456789abcdef")


def definir_ativo(
    dono: object,
    mapa: Mapping[str, str] | None,
    por_peca: Mapping[str, Mapping[str, str] | None] | None = None,
) -> None:
    """Guarda o mapa ATIVO no dono (o `StateStore` do daemon). Vazio = sem troca.

    ``por_peca`` é a troca JÁ JUNTADA de cada controle que tem a sua (``{uniq: mapa}``); um
    mapa vazio quer dizer «este controle não troca nada», mesmo com o perfil trocando.
    """
    if dono is None:
        return
    setattr(dono, _ATRIBUTO_DO_ATIVO,
            MappingProxyType(dict(mapa)) if mapa else None)
    limpo = {chave(u): MappingProxyType(dict(m or {}))
             for u, m in (por_peca or {}).items() if chave(u)}
    setattr(dono, _ATRIBUTO_POR_PECA, MappingProxyType(limpo))


def ativo(dono: object) -> Mapping[str, str] | None:
    """O mapa ativo, ou `None`. Leitura de memória, custo de um `getattr`."""
    valor = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if type(valor) is not MappingProxyType:
        return None
    return cast("Mapping[str, str]", valor)


def da_peca(dono: object, uniq: object) -> Mapping[str, str] | None:
    """A troca do controle ``uniq`` AGORA: a dele, ou a do perfil; ``None`` = nenhuma."""
    por_peca = getattr(dono, _ATRIBUTO_POR_PECA, None)
    if isinstance(por_peca, Mapping) and uniq:
        k = chave(uniq)
        if k in por_peca:
            return por_peca[k] or None
    return ativo(dono)


def alguma(dono: object) -> bool:
    """Algum controle troca botão neste perfil? Custo de dois ``getattr``."""
    if ativo(dono):
        return True
    por_peca = getattr(dono, _ATRIBUTO_POR_PECA, None)
    return isinstance(por_peca, Mapping) and any(por_peca.values())


__all__ = [
    "BOTAO_PS",
    "DESTINO_TOUCHPAD",
    "FORA_DO_ALCANCE",
    "FORCA_CHEIA",
    "GATILHOS",
    "MOTIVO_COLISAO",
    "MOTIVO_DESCONHECIDO",
    "MOTIVO_FORA",
    "MOTIVO_PS",
    "REMAPEAVEIS",
    "RemapeamentoRecusadoError",
    "alguma",
    "ativo",
    "chave",
    "da_peca",
    "definir_ativo",
    "juntar",
    "resolver",
    "resolver_da_peca",
    "traduzir",
]
