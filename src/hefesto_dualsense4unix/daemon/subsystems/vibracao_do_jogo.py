"""A vibração que o jogo pede a cada controle, dita no barramento (``jogo.vibracao``).

Desde 13/10/2026 (`test_a_vibracao_de_cada_controle_vira_evento.py`). Uma modificação com a
permissão ``ler:jogo.vibracao`` acompanha o que o jogo manda a CADA controle: o
``uniq`` dele, o número do jogador, o par pedido e o par que chegou aos motores.

O evento sai de ``apply_game_rumble``, o ponto por onde passa todo rumble do jogo
(o pad do P1, os de P2 a P4, o par fixado que vence), e tem duas regras de ritmo,
as que seguram o prazo do outro lado:

* **a batida**: enquanto o par efetivo for diferente de zero, o evento se repete a
  cada 250 ms, mesmo que o jogo não mande nada novo. Quem acompanha a vibração
  para o aparelho dele quando a batida some (o serviço caiu, o jogo travou);
* **o teto**: no máximo 60 por segundo por controle. O que a pressa atrasa não se
  perde: fica pendente e sai no tique seguinte, e o último valor, sobretudo o zero,
  sempre chega.

``efetivo`` é o que o jogo conseguiu pôr nos motores: ``[0, 0]`` quando o par
fixado pela tela vence ou a escrita foi recusada. A batida segue o ``efetivo``; o
``pedido`` é informação. A ordem dos pares é ``[fraco, forte]``, a de
``rumble.set``. ``t`` é o ``time.monotonic()`` do serviço, que o resto da máquina
lê igual.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

PERIODO_DA_BATIDA_S = 0.25
INTERVALO_MINIMO_S = 1.0 / 60.0

_ATRIBUTO = "_vibracao_do_jogo_vista"
_TRAVA_DA_CRIACAO = threading.Lock()

Par = tuple[int, int]


@dataclass
class _Linha:
    """O último que o jogo disse a UM controle, e o que falta dizer dele."""

    jogador: int | None
    pedido: Par
    efetivo: Par
    enviado_em: float
    pendente: bool
    jogo: Par = (0, 0)
    toques: Par = (0, 0)
    motores: Par = (0, 0)


class _Vista:
    """Os controles que o jogo faz vibrar agora, com a trava de quem escreve e de quem bate."""

    def __init__(self) -> None:
        self.linhas: dict[str, _Linha] = {}
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
        except AttributeError as exc:
            logger.debug("jogo_vibracao_sem_tabela", err=str(exc))
            return None
    return vista


def _par(valor: object) -> Par:
    if isinstance(valor, tuple) and len(valor) == 2:
        return (int(valor[0]), int(valor[1]))
    return (0, 0)


def _uniq_do_pedido(daemon: Any, target_uniq: str | None) -> str | None:
    """O controle que o pedido mira; sem endereço, o primário (mesa de um controle só)."""
    if isinstance(target_uniq, str) and target_uniq:
        return target_uniq
    primario = getattr(getattr(daemon, "controller", None), "primary_uniq", None)
    if callable(primario):
        primario = primario()
    return primario if isinstance(primario, str) and primario else None


def _jogador_de(daemon: Any, uniq: str | None) -> int | None:
    """O número do jogador que o controle acende agora (leitura pura, nunca aloca lugar)."""
    if uniq is None:
        return None
    registro = getattr(daemon, "identity_registry", None)
    perguntar = getattr(registro, "numero_da_lampada", None)
    if callable(perguntar):
        try:
            bruto = perguntar(uniq, assign=False)
        except Exception as exc:
            logger.debug("jogo_vibracao_sem_numero", uniq=uniq, err=str(exc))
        else:
            if isinstance(bruto, int) and not isinstance(bruto, bool) and bruto >= 1:
                return bruto
    from hefesto_dualsense4unix.daemon.subsystems.base import slot_de_sessao

    slot = slot_de_sessao(daemon, uniq)
    return slot if slot is not None and slot >= 1 else None


def _publicar(daemon: Any, uniq: str | None, linha: _Linha, agora: float) -> None:
    publicar = getattr(getattr(daemon, "bus", None), "publish", None)
    if not callable(publicar):
        return
    try:
        publicar(
            EventTopic.JOGO_VIBRACAO,
            {
                "uniq": uniq,
                "jogador": linha.jogador,
                "pedido": list(linha.pedido),
                "efetivo": list(linha.efetivo),
                "jogo": list(linha.jogo),
                "toques": list(linha.toques),
                "t": agora,
            },
        )
    except Exception as exc:
        logger.debug("jogo_vibracao_nao_publicada", uniq=uniq, err=str(exc))


def dizer_a_vibracao(
    daemon: Any,
    target_uniq: str | None,
    pedido: Par,
    efetivo: Par | None,
    *,
    agora: float | None = None,
    jogo: Par | None = None,
    toques: Par | None = None,
    motores: Par | None = None,
) -> None:
    """Diz no barramento o que o jogo pediu a um controle e o que chegou aos motores.

    ``efetivo`` ``None`` é «nada foi escrito» (o par fixado venceu, a escrita foi
    recusada) e sai como ``[0, 0]``. ``jogo`` e ``toques`` são ``(esquerdo, direito)``: o que o
    jogo pôs nos motores e o que os meus toques puseram (sem ``jogo``, é o ``efetivo``).
    ``motores`` é o ``(fraco, forte)`` que ficou nos motores do HID (sem ele, o ``efetivo``).
    Nunca levanta: o rumble do jogo não espera por quem escuta.
    """
    try:
        _dizer(daemon, target_uniq, _par(pedido), _par(efetivo), agora, jogo, toques, motores)
    except Exception as exc:
        logger.debug("jogo_vibracao_nao_dita", err=str(exc))


def _dizer(
    daemon: Any,
    target_uniq: str | None,
    pedido: Par,
    efetivo: Par,
    agora: float | None,
    jogo: Par | None = None,
    toques: Par | None = None,
    motores: Par | None = None,
) -> None:
    uniq = _uniq_do_pedido(daemon, target_uniq)
    chave = uniq or ""
    agora = time.monotonic() if agora is None else agora
    vista = _vista_do(daemon, criar=True)
    if vista is None:
        return
    jogador = _jogador_de(daemon, uniq)
    lados = _par(jogo) if jogo is not None else (efetivo[1], efetivo[0])
    dos_toques = _par(toques) if toques is not None else (0, 0)
    nos_motores = _par(motores) if motores is not None and efetivo != (0, 0) else efetivo
    with vista.trava:
        linha = vista.linhas.get(chave)
        if linha is None and pedido == (0, 0) and efetivo == (0, 0):
            return
        if linha is None:
            linha = vista.linhas[chave] = _Linha(
                jogador, pedido, efetivo, enviado_em=agora - 1.0, pendente=True,
                jogo=lados, toques=dos_toques, motores=nos_motores,
            )
        else:
            linha.jogador, linha.pedido, linha.efetivo, linha.pendente = (
                jogador, pedido, efetivo, True,
            )
            linha.jogo, linha.toques, linha.motores = lados, dos_toques, nos_motores
        if agora - linha.enviado_em < INTERVALO_MINIMO_S:
            return
        linha.enviado_em, linha.pendente = agora, False
        a_dizer = _Linha(**vars(linha))
        if efetivo == (0, 0):
            del vista.linhas[chave]
    _publicar(daemon, uniq or None, a_dizer, agora)


def par_nos_motores(daemon: Any, uniq: str) -> Par:
    """O ``(fraco, forte)`` que o jogo deixou nos motores de ``uniq``; ``(0, 0)`` sem jogo vibrando.

    Quem toca por cima do jogo (o toque do gesto dos acessórios) soma a este par e o devolve no
    fim, em vez de calar o jogo até o quadro seguinte dele. Nunca levanta.
    """
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    vista = _vista_do(daemon, criar=False)
    alvo = norm_mac(uniq)
    if vista is None or alvo is None:
        return (0, 0)
    try:
        with vista.trava:
            for chave, linha in vista.linhas.items():
                if chave and norm_mac(chave) == alvo:
                    return linha.motores
    except Exception as exc:
        logger.debug("jogo_vibracao_par_ilegivel", err=str(exc))
    return (0, 0)


def bater_a_vibracao(daemon: Any, agora: float | None = None) -> None:
    """A batida e o que o teto atrasou: chamada a cada tique do poll loop. Nunca levanta."""
    vista = _vista_do(daemon, criar=False)
    if vista is None or not vista.linhas:
        return
    agora = time.monotonic() if agora is None else agora
    a_dizer: list[tuple[str, _Linha]] = []
    with vista.trava:
        for chave, linha in list(vista.linhas.items()):
            desde = agora - linha.enviado_em
            repete = linha.efetivo != (0, 0) and desde >= PERIODO_DA_BATIDA_S
            if not ((linha.pendente and desde >= INTERVALO_MINIMO_S) or repete):
                continue
            linha.enviado_em, linha.pendente = agora, False
            a_dizer.append((chave, _Linha(**vars(linha))))
            if linha.efetivo == (0, 0):
                del vista.linhas[chave]
    for chave, linha in a_dizer:
        _publicar(daemon, chave or None, linha, agora)


def esquecer_a_vibracao(
    daemon: Any, target_uniq: str | None = None, *, agora: float | None = None
) -> None:
    """O fim da sessão do pad (um controle) ou do jogo (todos): a batida para.

    O controle que ainda vibrava, para quem acompanha, recebe o zero que faltou. Toda linha
    da tabela é um controle cujo último evento DITO não foi zero (o zero dito apaga a linha),
    inclusive a que guarda um zero que o teto atrasou: todas recebem o zero.
    """
    vista = _vista_do(daemon, criar=False)
    if vista is None or not vista.linhas:
        return
    agora = time.monotonic() if agora is None else agora
    if target_uniq is None:
        chaves = list(vista.linhas)
    else:
        chaves = [_uniq_do_pedido(daemon, target_uniq) or ""]
    zeros: list[tuple[str, _Linha]] = []
    with vista.trava:
        for chave in chaves:
            linha = vista.linhas.pop(chave, None)
            if linha is not None:
                zeros.append((chave, _Linha(linha.jogador, (0, 0), (0, 0), agora, False)))
    for chave, linha in zeros:
        _publicar(daemon, chave or None, linha, agora)
