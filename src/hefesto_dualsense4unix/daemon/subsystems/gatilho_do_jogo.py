"""O efeito de gatilho que o jogo escreve a cada controle, dito no barramento (``jogo.gatilho``).

O-GATILHO-E-A-HAPTICA-DO-JOGO-VIRAM-EVENTOS-PARA-AS-EXTENSOES-01. O evento sai de
``apply_game_trigger``, por onde passa todo gatilho do jogo (P1 a P4): o bloco de 11 bytes vira
``{uniq, jogador, lado, modo, forca, posicao, t}`` (a tabela de bytes é a da referência
canônica, «O empacotamento dos 11 bytes»; o vocabulário, o da porta das modificações). Sai uma
vez por mudança, com teto de 50 por segundo por lado: o que o teto atrasa sai no tique seguinte,
e o último valor sempre chega. O fim da sessão do pad ou do jogo manda o ``desligado`` que
faltava a quem ainda tinha efeito.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O teto de eventos por lado de cada controle: 50 por segundo.
INTERVALO_MINIMO_S = 1.0 / 50.0

TAMANHO_DO_BLOCO = 11
ZONAS_DO_CURSO = 10

DESLIGADO = "desligado"

#: O lado como o evento o diz; o gatilho do jogo chega como `left`/`right`.
_LADO = {"left": "esquerdo", "right": "direito"}

_ATRIBUTO = "_gatilho_do_jogo_visto"
_TRAVA_DA_CRIACAO = threading.Lock()

Decodificado = tuple[str, float, float]


def _zonas(bloco: bytes) -> list[int]:
    """As zonas do curso ligadas na máscara dos bytes 1-2 (u16 little-endian)."""
    mascara = bloco[1] | (bloco[2] << 8)
    return [z for z in range(ZONAS_DO_CURSO) if mascara & (1 << z)]


def _forca_por_zona(bloco: bytes, zonas: list[int]) -> list[int]:
    """As forças de 3 bits das zonas ligadas (bytes 3-6, valor = força - 1), de 1 a 8."""
    empacotado = bloco[3] | (bloco[4] << 8) | (bloco[5] << 16) | (bloco[6] << 24)
    return [((empacotado >> (3 * z)) & 0x07) + 1 for z in zonas]


def _forca_do_maior(bloco: bytes, zonas: list[int]) -> float:
    return max(_forca_por_zona(bloco, zonas)) / 8.0


def _forca_do_byte_3(bloco: bytes, _zonas: list[int]) -> float:
    return ((bloco[3] & 0x07) + 1) / 8.0


def _forca_das_duas_amplitudes(bloco: bytes, _zonas: list[int]) -> float:
    return (max(bloco[3] & 0x07, (bloco[3] >> 3) & 0x07) + 1) / 8.0


def _forca_do_galope(_bloco: bytes, _zonas: list[int]) -> float:
    return 1.0  # o bloco carrega os pés e a frequência, não uma força


def _leitor(
    nome: str, forca_de: Callable[[bytes, list[int]], float]
) -> Callable[[bytes], Decodificado]:
    def _ler(bloco: bytes) -> Decodificado:
        zonas = _zonas(bloco)
        if not zonas:
            return (DESLIGADO, 0.0, 0.0)
        posicao = zonas[0] / (ZONAS_DO_CURSO - 1)
        return (nome, round(forca_de(bloco, zonas), 4), round(posicao, 4))

    return _ler


def _desligado(_bloco: bytes) -> Decodificado:
    return (DESLIGADO, 0.0, 0.0)


def _legado(bloco: bytes) -> Decodificado:
    """Um primeiro byte que a referência não decodifica: ligado ou não, sem força nem posição."""
    return ("outro", 1.0 if any(bloco[1:]) else 0.0, 0.0)


#: O leitor de cada modo pelo primeiro byte do bloco; o que não está aqui é ``outro``.
_LEITOR_POR_BYTE: dict[int, Callable[[bytes], Decodificado]] = {
    0x00: _desligado,
    0x05: _desligado,
    0x21: _leitor("resistencia", _forca_do_maior),  # (noqa-acento): contrato ASCII
    0x22: _leitor("arco", _forca_do_byte_3),
    0x23: _leitor("galope", _forca_do_galope),
    0x25: _leitor("arma", _forca_do_byte_3),
    0x26: _leitor("vibracao", _forca_do_maior),
    0x27: _leitor("metralhadora", _forca_das_duas_amplitudes),
}


def decodificar_o_bloco(bloco: bytes) -> Decodificado:
    """``(modo, força, posição)`` de um bloco de gatilho de 11 bytes.

    Bloco curto, ou com a máscara de zonas vazia, é ``desligado``. Nunca levanta.
    """
    if len(bloco) < TAMANHO_DO_BLOCO:
        return _desligado(bloco)
    return _LEITOR_POR_BYTE.get(bloco[0], _legado)(bloco)


@dataclass
class _Linha:
    """O último bloco dito de UM lado de UM controle, e o que falta dizer dele."""

    bloco: bytes
    ligada: bool
    enviado_em: float
    pendente: bytes | None


class _Vista:
    def __init__(self) -> None:
        self.linhas: dict[tuple[str, str], _Linha] = {}
        self.trava = threading.Lock()


def _vista_do(daemon: Any, *, criar: bool) -> _Vista | None:
    vista = getattr(daemon, _ATRIBUTO, None)
    if isinstance(vista, _Vista):
        return vista
    if not criar:
        return None
    with _TRAVA_DA_CRIACAO:
        vista = getattr(daemon, _ATRIBUTO, None)
        if isinstance(vista, _Vista):
            return vista
        vista = _Vista()
        try:
            setattr(daemon, _ATRIBUTO, vista)
        except AttributeError as exc:  # um dublê sem lugar para a tabela: sem evento, sem erro
            logger.debug("jogo_gatilho_sem_tabela", err=str(exc))
            return None
    return vista


def _publicar(
    daemon: Any, uniq: str, lado: str, bloco: bytes, agora: float
) -> None:
    publicar = getattr(getattr(daemon, "bus", None), "publish", None)
    if not callable(publicar):
        return
    from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

    modo, forca, posicao = decodificar_o_bloco(bloco)
    try:
        publicar(
            EventTopic.JOGO_GATILHO,
            {
                "uniq": uniq,
                "jogador": _jogador_de(daemon, uniq),
                "lado": _LADO.get(lado, lado),
                "modo": modo,
                "forca": forca,
                "posicao": posicao,
                "t": agora,
            },
        )
    except Exception as exc:
        logger.debug("jogo_gatilho_nao_publicado", uniq=uniq, err=str(exc))


def dizer_o_gatilho(
    daemon: Any,
    target_uniq: str | None,
    lado: str,
    bloco: bytes,
    *,
    agora: float | None = None,
) -> None:
    """Diz no barramento o gatilho que o jogo escreveu a um controle. Nunca levanta.

    Sem ``target_uniq`` o pedido mira o primário (mesa de um controle só); sem nenhum dos
    dois não há de quem falar e nada sai.
    """
    try:
        _dizer(daemon, target_uniq, lado, bytes(bloco), agora)
    except Exception as exc:
        logger.debug("jogo_gatilho_nao_dito", err=str(exc))


def _dizer(
    daemon: Any, target_uniq: str | None, lado: str, bloco: bytes, agora: float | None
) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _uniq_do_pedido

    uniq = _uniq_do_pedido(daemon, target_uniq)
    if uniq is None:
        return
    agora = time.monotonic() if agora is None else agora
    vista = _vista_do(daemon, criar=True)
    if vista is None:
        return
    chave = (uniq, lado)
    with vista.trava:
        linha = vista.linhas.get(chave)
        if linha is None:
            if decodificar_o_bloco(bloco)[0] == DESLIGADO:
                return  # nada ligado e nada se liga: não há o que dizer
            # `agora - 1.0`: o primeiro de um lado nunca espera o teto.
            linha = vista.linhas[chave] = _Linha(
                b"", False, enviado_em=agora - 1.0, pendente=None
            )
        if bloco == linha.bloco and linha.pendente is None:
            return  # o jogo reescreveu o mesmo gatilho
        if agora - linha.enviado_em < INTERVALO_MINIMO_S:
            linha.pendente = bloco  # o tique seguinte diz (`bater_o_gatilho`)
            return
        linha.bloco, linha.pendente, linha.enviado_em = bloco, None, agora
        linha.ligada = decodificar_o_bloco(bloco)[0] != DESLIGADO
    _publicar(daemon, uniq, lado, bloco, agora)


def bater_o_gatilho(daemon: Any, agora: float | None = None) -> None:
    """O que o teto atrasou: chamada a cada tique do poll loop. Nunca levanta."""
    vista = _vista_do(daemon, criar=False)
    if vista is None or not vista.linhas:
        return
    agora = time.monotonic() if agora is None else agora
    a_dizer: list[tuple[str, str, bytes]] = []
    with vista.trava:
        for (uniq, lado), linha in list(vista.linhas.items()):
            pendente = linha.pendente
            if pendente is None or agora - linha.enviado_em < INTERVALO_MINIMO_S:
                continue
            linha.bloco, linha.pendente, linha.enviado_em = pendente, None, agora
            linha.ligada = decodificar_o_bloco(pendente)[0] != DESLIGADO
            a_dizer.append((uniq, lado, pendente))
    for uniq, lado, bloco in a_dizer:
        _publicar(daemon, uniq, lado, bloco, agora)


def esquecer_o_gatilho(
    daemon: Any, target_uniq: str | None = None, *, agora: float | None = None
) -> None:
    """O fim da sessão do pad (um controle) ou do jogo (todos): o gatilho se desliga.

    Quem ainda tinha efeito recebe o ``desligado`` que faltava, inclusive o lado cujo último
    bloco o teto atrasou. Quem já estava ``desligado`` não recebe nada: o zero já foi dito.
    """
    vista = _vista_do(daemon, criar=False)
    if vista is None or not vista.linhas:
        return
    agora = time.monotonic() if agora is None else agora
    if target_uniq is None:
        alvo: str | None = None
    else:
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import (
            _uniq_do_pedido,
        )

        alvo = _uniq_do_pedido(daemon, target_uniq)
        if alvo is None:
            return
    zeros: list[tuple[str, str]] = []
    with vista.trava:
        for (uniq, lado) in list(vista.linhas):
            if alvo is not None and uniq != alvo:
                continue
            linha = vista.linhas.pop((uniq, lado))
            if linha.ligada or (
                linha.pendente is not None
                and decodificar_o_bloco(linha.pendente)[0] != DESLIGADO
            ):
                zeros.append((uniq, lado))
    for uniq, lado in zeros:
        _publicar(daemon, uniq, lado, bytes(TAMANHO_DO_BLOCO), agora)
