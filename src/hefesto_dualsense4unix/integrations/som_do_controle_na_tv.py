"""«Tudo na TV e Nada no Controle» — e o «tudo» inclui o som DO controle."""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import marca_do_aparelho
from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos

__all__ = ["desligar", "desligar_todos", "esta_ligado", "ligados", "ligar"]

_LACOS = Lacos("som-do-controle-na-tv")


def esta_ligado(uniq: str) -> bool:
    """O som deste controle está saindo na TV AGORA?"""
    return _LACOS.esta_ligado(marca_do_aparelho(uniq))


def ligados() -> tuple[str, ...]:
    """As marcas dos aparelhos cujo som está indo para a TV, em ordem estável."""
    return _LACOS.ligados()


def ligar(uniq: str, *, destino: str = "") -> bool:
    """Manda o som deste controle para a TV. `True` = de pé."""
    sink = nome_do_sink(uniq)
    if not sink:
        return False
    return _LACOS.ligar(
        marca_do_aparelho(uniq), captura=f"{sink}.monitor", destino=destino,
        canais=2, mapa="[ FL FR ]")


def desligar(uniq: str) -> bool:
    """Para de mandar o som deste controle para a TV."""
    return _LACOS.desligar(marca_do_aparelho(uniq))


def desligar_todos() -> int:
    """Fecha todos os laços deste eixo e devolve quantos eram."""
    return _LACOS.desligar_todos()
