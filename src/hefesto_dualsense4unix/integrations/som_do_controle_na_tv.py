"""«Tudo na TV e Nada no Controle» — e o «tudo» inclui o som DO controle."""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink
from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos

__all__ = ["desligar", "desligar_todos", "esta_ligado", "ligados", "ligar"]

_LACOS = Lacos("som-do-controle-na-tv")


def esta_ligado(uniq: str) -> bool:
    """O som deste controle está saindo na TV AGORA?"""
    return _LACOS.esta_ligado(uniq)


def ligados() -> tuple[str, ...]:
    """Os `uniq` cujo som está indo para a TV, em ordem estável."""
    return _LACOS.ligados()


def ligar(uniq: str, *, destino: str = "") -> bool:
    """Manda o som deste controle para a TV. `True` = de pé."""
    sink = nome_do_sink(uniq)
    if not sink:
        return False
    return _LACOS.ligar(
        uniq, captura=f"{sink}.monitor", destino=destino,
        canais=2, mapa="[ FL FR ]")


def desligar(uniq: str) -> bool:
    """Para de mandar o som deste controle para a TV."""
    return _LACOS.desligar(uniq)


def desligar_todos() -> int:
    """Fecha todos os laços deste eixo e devolve quantos eram."""
    return _LACOS.desligar_todos()
