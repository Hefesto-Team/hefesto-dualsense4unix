"""O 🎙 ligado — você se ouve enquanto ele está verde."""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.laco_de_audio import LATENCIA_MS, Lacos

__all__ = [
    "LATENCIA_MS",
    "desligar",
    "desligar_todos",
    "esta_ligado",
    "ligados",
    "ligar",
]

_LACOS = Lacos("retorno-do-mic")


def esta_ligado(uniq: str) -> bool:
    """O retorno deste controle está de pé AGORA?"""
    return _LACOS.esta_ligado(uniq)


def ligados() -> tuple[str, ...]:
    """Os `uniq` com retorno de pé, em ordem estável."""
    return _LACOS.ligados()


def ligar(uniq: str, fonte: str, *, destino: str = "") -> bool:
    """Liga o retorno deste controle. `True` = de pé.

    :param fonte: o nó de captura daquele controle (`hefesto_mic_<hex6>`).
    :param destino: o sink de saída; vazio manda para a saída padrão, que é
        onde ela ouve o jogo — e é a única resposta útil a *"como eu soo"*.

    **MONO, e o mapa vai escrito**: o microfone do DualSense é um canal só, e
    deixar o PipeWire adivinhar o mapa produz um laço estéreo com metade muda.
    """
    if not uniq or not fonte:
        return False
    return _LACOS.ligar(
        uniq, captura=fonte, destino=destino, canais=1, mapa="[ MONO ]")


def desligar(uniq: str) -> bool:
    """Desliga o retorno deste controle. `True` = havia um e ele morreu."""
    return _LACOS.desligar(uniq)


def desligar_todos() -> int:
    """Desliga todos os retornos de voz e devolve quantos eram."""
    return _LACOS.desligar_todos()
