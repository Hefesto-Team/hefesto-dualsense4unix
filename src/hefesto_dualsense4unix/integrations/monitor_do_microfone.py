"""O 🎙 ligado — você se ouve enquanto ele está verde."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import marca_do_aparelho
from hefesto_dualsense4unix.integrations.laco_de_audio import LATENCIA_MS, Lacos

__all__ = [
    "LATENCIA_MS",
    "ROTA_NO_CONTROLE",
    "desligar",
    "desligar_todos",
    "destino_da_rota",
    "destino_de",
    "esta_ligado",
    "ligados",
    "ligar",
    "seguir",
]

_LACOS = Lacos("retorno-do-mic")


def esta_ligado(uniq: str) -> bool:
    """O retorno deste controle está de pé AGORA?"""
    return _LACOS.esta_ligado(marca_do_aparelho(uniq))


def ligados() -> tuple[str, ...]:
    """As marcas dos aparelhos com retorno de pé, em ordem estável."""
    return _LACOS.ligados()


def ligar(uniq: str, fonte: str, *, destino: str = "") -> bool:
    """Liga o retorno deste controle. `True` = de pé.

    :param fonte: o nó de captura daquele controle (`hefesto_mic_<marca>`).
    :param destino: o sink de saída, o que a rota do cartão escolhe
        (:func:`destino_da_rota`); vazio manda para a saída padrão.

    **MONO, e o mapa vai escrito**: o microfone do DualSense é um canal só, e
    deixar o PipeWire adivinhar o mapa produz um laço estéreo com metade muda.
    """
    marca = marca_do_aparelho(uniq)
    if not marca or not fonte:
        return False
    return _LACOS.ligar(
        marca, captura=fonte, destino=destino, canais=1, mapa="[ MONO ]")


def desligar(uniq: str) -> bool:
    """Desliga o retorno deste controle. `True` = havia um e ele morreu."""
    return _LACOS.desligar(marca_do_aparelho(uniq))


def desligar_todos() -> int:
    """Desliga todos os retornos de voz e devolve quantos eram."""
    return _LACOS.desligar_todos()


ROTA_NO_CONTROLE = "pc"


def destino_da_rota(
    rota: str,
    *,
    sink_do_controle: str,
    sink_padrao: str,
    anterior: str,
    sinks: Iterable[str],
    e_de_controle: Callable[[str], bool],
) -> str:
    """Onde o retorno deste controle toca, pela rota escolhida no cartão. PURA.

    Com todo o som no controle (``"pc"``), no alto-falante dele. Nas outras
    rotas, no PC: a saída padrão que não é de controle nenhum; senão a que a
    rota guardou antes de mandar o som a um controle; senão a primeira saída
    que não é de controle nem desta casa. "" = a saída padrão.
    """
    if rota == ROTA_NO_CONTROLE and sink_do_controle:
        return sink_do_controle
    for candidato in (sink_padrao, anterior):
        if candidato and not e_de_controle(candidato):
            return candidato
    for sink in sinks:
        if sink and not sink.startswith("hefesto") and not e_de_controle(sink):
            return sink
    return ""


def destino_de(uniq: str) -> str | None:
    """O destino do retorno de pé deste controle; ``None`` sem retorno."""
    return _LACOS.destino_de(marca_do_aparelho(uniq))


def seguir(uniq: str, destino: str) -> bool:
    """O retorno de pé passa a tocar em ``destino``. ``True`` = trocou agora."""
    return _LACOS.seguir(marca_do_aparelho(uniq), destino)
