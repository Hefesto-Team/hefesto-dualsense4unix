"""Grava o que ela declarou DIRETO NO DISCO — sem daemon, sem IPC.

O DEFEITO QUE ESTE MÓDULO FECHA
-------------------------------

``utils/maquina.py`` ganhou ``gravar_rascunho_da_mesa`` em 24/08/2026, escrita
exatamente para uma tela que grava a cada resposta. Ela nasceu com **zero
chamadores** (§7.3 da ``CALIBRAR-AS-ENTRADAS-01``): o único escritor de produção
do ``maquina.json`` é o handler ``machine.declare``, atrás do IPC. Com o daemon
parado, **nada do que ela declara é gravado** — e a tela responde "não gravei o
que você declarou" para uma coisa que não depende de daemon nenhum.

É a ``A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ`` no meio do caminho da calibração: a cura
estava escrita e nunca foi ligada. Este módulo é o chamador que faltava.

POR QUE A GRAVAÇÃO NÃO PODE ESPERAR O "APLICAR"
------------------------------------------------

A calibração é uma cerimônia abandonável: ``[Já chega por hoje]`` em todo passo,
``Esc`` fazendo o mesmo, sem "tem certeza?" e sem resumo do que faltou (§4.4).
Isso só é honesto se **nenhuma saída perder trabalho** — logo cada resposta vai
ao disco na hora (R28), e matar o processo no meio não custa nada.

O CONTRATO É "NUNCA LEVANTA"
-----------------------------

Quem chama é uma janela GTK dentro de um handler de clique: uma exceção ali
derruba o passo e leva junto a resposta que a pessoa acabou de dar.
``gravar_maquina_com_descartes`` levanta ``ValueError`` quando a declaração não
passa no schema e ``OSError`` quando a escrita falha; :func:`declarar_a_mesa`
traduz as três respostas possíveis em :class:`Recibo`, e o motivo é um token de
máquina — **a redação de tela não é deste módulo**, é da
``CONFIGURACOES-O-LEXICO-01``, dona única do texto da aba.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import gravar_rascunho_da_mesa

logger = get_logger(__name__)

#: O arquivo em disco tem uma ``version`` que não é a nossa. Nada foi lido nem
#: escrito, e os bytes dela continuam intactos — escolha de alguém não se
#: destrói para registrar outra.
MOTIVO_VERSAO_ESTRANHA = "versao_estranha"

#: A declaração não passou no schema. É defeito de quem chama, não da mesa: o
#: valor nunca chegou ao disco, e o log diz qual campo.
MOTIVO_SCHEMA_RECUSOU = "schema_recusou"

#: O disco recusou a escrita (permissão, espaço, ponto de montagem sumido).
MOTIVO_DISCO = "disco"


@dataclass(frozen=True)
class Recibo:
    """O que a gravação fez. ``motivo`` é ``""`` exatamente quando ``gravou``."""

    gravou: bool
    motivo: str = ""


def declarar_a_mesa(declaracao: Mapping[str, Any]) -> Recibo:
    """Funde a declaração na seção ``mesa`` do ``maquina.json``. **Nunca levanta.**

    Chamada uma vez por resposta, não uma vez por cerimônia: a fusão de
    ``gravar_maquina`` desce nos dicionários aninhados, então declarar um campo
    não apaga os outros — nem o orçamento, nem os controles, nem o que outra
    seção da aba gravou um segundo antes.

    Não há caminho de IPC aqui, e é o ponto todo: com o daemon parado, esta
    função grava do mesmo jeito. ``tests/unit/test_a_calibracao_grava_com_o_
    daemon_morto.py`` é o portão que segura essa porta fechada.
    """
    try:
        gravou = gravar_rascunho_da_mesa(declaracao)
    except ValueError as exc:
        logger.warning("lugar_declarado_schema_recusou", err=str(exc))
        return Recibo(False, MOTIVO_SCHEMA_RECUSOU)
    except OSError as exc:
        logger.warning("lugar_declarado_disco_recusou", err=str(exc))
        return Recibo(False, MOTIVO_DISCO)
    if not gravou:
        logger.warning("lugar_declarado_versao_estranha")
        return Recibo(False, MOTIVO_VERSAO_ESTRANHA)
    logger.debug("lugar_declarado_gravado", campos=sorted(declaracao))
    return Recibo(True)


__all__ = [
    "MOTIVO_DISCO",
    "MOTIVO_SCHEMA_RECUSOU",
    "MOTIVO_VERSAO_ESTRANHA",
    "Recibo",
    "declarar_a_mesa",
]
